"""
Supervisor stage nodes.

Each stage is intentionally narrow: query analysis, entity resolution,
SPARQL generation, execution, sparse relation completion, and answer writing.
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.agents.llm_client import call_llm
from app.agents.state import AgentState
from app.agents.tools.entity_tools import (
    resolve_korean_name,
    resolve_person_entity,
    resolve_place_entity,
)
from app.agents.tools.execution_tools import execute_sparql_on_fuseki, verify_results_quality
from app.agents.tools.link_prediction_tools import predict_sparse_relations
from app.agents.tools.sparql_tools import generate_sparql, verify_sparql_syntax


def query_analysis_stage(state: AgentState) -> Dict[str, Any]:
    """Extract intent, entities, time hints, and target relation."""
    print("\n[STAGE] Query Analysis")

    query = state["query"]

    analysis_prompt = f"""
다음 질의를 JSON으로 분석하세요.

질의: "{query}"

필드:
1. intent: recent_calls, most_used_app, visited_places, call_after_cafe, meeting_location, photos_at_place, sparse_completion 중 하나
2. target_relation: visitedAfter, metDuring, relatedEvent, usedDuring 중 하나. 없으면 null
3. time_constraint: 어제, 최근, 지난주 등 상대 시간. 없으면 null
4. person_mention: 언급된 사람 이름. 없으면 null
5. place_type: 카페, 식당, 회사 같은 장소 유형. 없으면 null
6. place_mention: 스타벅스, 투썸플레이스 같은 구체 장소명. 없으면 null
7. event_title: 디자인 리뷰 같은 일정/회의 제목. 없으면 null

JSON만 출력하세요:
{{
  "intent": "...",
  "target_relation": "...",
  "time_constraint": "...",
  "person_mention": "...",
  "place_type": "...",
  "place_mention": "...",
  "event_title": "..."
}}
"""

    result = call_llm(
        system_prompt="당신은 스마트폰 로그 질의 분석 전문가입니다.",
        user_prompt=analysis_prompt,
        temperature=0.1,
    )

    analysis = _parse_json_safe(result)

    intent = _none_if_null(analysis.get("intent")) or _infer_intent_from_query(query)

    # LLM이 유효하지 않은 값을 반환할 수 있으므로, 유효한 관계명인지 검증 후 fallback 적용
    LINK_PREDICTION_RELATIONS = {"visitedAfter", "metDuring", "relatedEvent", "usedDuring"}
    _llm_relation = _none_if_null(analysis.get("target_relation"))
    if _llm_relation in LINK_PREDICTION_RELATIONS:
        target_relation = _llm_relation
    else:
        # LLM이 유효하지 않거나 null → rule-based로 확실하게 결정
        target_relation = _infer_target_relation_from_query(query)

    person_mention = _none_if_null(analysis.get("person_mention")) or _extract_person_mention(query)
    place_type = _normalize_place_type(_none_if_null(analysis.get("place_type"))) or _extract_place_type(query)
    place_mention = _none_if_null(analysis.get("place_mention")) or _extract_place_mention(query)
    event_title = _none_if_null(analysis.get("event_title")) or _extract_event_title(query)

    if person_mention:
        eng_name = resolve_korean_name(person_mention)
        if eng_name != person_mention:
            print(f"  [Analysis] name normalized: {person_mention} -> {eng_name}")
            person_mention = eng_name

    entities = {
        "person": person_mention,
        "place_type": place_type,
        "place_mention": place_mention,
        "event_title": event_title,
    }

    time_constraint = _build_time_constraint(_none_if_null(analysis.get("time_constraint")))

    print(f"  Intent: {intent}")
    print(f"  Target relation: {target_relation} (LLM={_llm_relation!r})")
    print(f"  Entities: {entities}")
    print(f"  Time: {time_constraint}")

    # target_relation이 있으면 LP 후보로 표시 (실제 트리거는 SPARQL 결과 0건 or sparse일 때)
    use_link_prediction = target_relation in LINK_PREDICTION_RELATIONS if target_relation else False

    if use_link_prediction:
        print(f"  [Analysis] target_relation={target_relation} → SPARQL 실행 후 결과 없으면 LP 대기")

    return {
        "intent": intent,
        "target_relation": target_relation,
        "entities": entities,
        "time_constraint": time_constraint,
        "workflow_path": ["query_analysis"],
        "resolved_entities": {},
        "sparql_results": None,
        "link_prediction_done": False,
        "sparql_retry_count": 0,
        "use_link_prediction": use_link_prediction,
    }


def entity_resolution_stage(state: AgentState) -> Dict[str, Any]:
    """Resolve person and place mentions to KG entities when available."""
    print("\n[STAGE] Entity Resolution")

    entities = state.get("entities", {})
    resolved = dict(state.get("resolved_entities", {}))

    person_name = entities.get("person")
    place_query = entities.get("place_mention") or entities.get("place_type")

    if person_name and not resolved.get("person"):
        person_result = resolve_person_entity(person_name)
        if person_result:
            resolved["person"] = person_result
            print(f"  Person resolved: {person_result.get('label')}")
        else:
            print(f"  Person '{person_name}' not found; using search text")
            resolved["person"] = {"uri": None, "label": person_name, "search_name": person_name}

    if place_query and not resolved.get("place"):
        place_results = resolve_place_entity(place_query)
        if place_results:
            resolved["place"] = place_results
            labels = [place.get("label", "") for place in place_results[:2]]
            print(f"  Place resolved: {labels}")
        else:
            print(f"  Place '{place_query}' not found")
            resolved["place"] = []

    return {
        "resolved_entities": resolved,
        "workflow_path": ["entity_resolution"],
    }


def sparql_generation_stage(state: AgentState) -> Dict[str, Any]:
    """Generate a SPARQL query from the current state."""
    print("\n[STAGE] SPARQL Generation")

    query = state["query"]
    entities_text = _format_entities_for_sparql_prompt(state)
    time_info = _format_time_info(state.get("time_constraint"))
    sparql_retry_count = state.get("sparql_retry_count", 0)

    sparql_query = generate_sparql(
        query=query,
        intent=state.get("intent", "unknown"),
        entities_text=entities_text,
        time_info=time_info,
        predicted_triples=state.get("predicted_triples") or None,
        prediction_confidence=state.get("prediction_confidence") or None,
        prediction_evidence=state.get("prediction_evidence") or None,
        target_relation=state.get("target_relation"),
    )

    validation = verify_sparql_syntax(sparql_query)
    if not validation["is_valid"]:
        print(f"  [WARNING] SPARQL syntax issue: {validation['error']}")

    return {
        "sparql_query": sparql_query,
        "sparql_results": None,
        "result_verification": None,
        "sparql_retry_count": sparql_retry_count + 1,
        "workflow_path": ["sparql_generation"],
    }


def execution_stage(state: AgentState) -> Dict[str, Any]:
    """Run SPARQL on Fuseki and verify result quality."""
    print("\n[STAGE] Execution")

    sparql_query = state.get("sparql_query", "")
    if not sparql_query:
        return {
            "sparql_results": [],
            "execution_time_ms": 0.0,
            "result_verification": {"is_complete": False, "issue": "empty", "suggestion": "SPARQL query missing"},
            "error": "SPARQL query missing",
            "workflow_path": ["execution"],
        }

    exec_result = execute_sparql_on_fuseki(sparql_query)
    results = exec_result["results"]
    verification = verify_results_quality(results)

    print(f"  Results: {len(results)} rows; quality={verification['issue']}")

    return {
        "sparql_results": results,
        "execution_time_ms": exec_result["execution_time_ms"],
        "result_verification": verification,
        "workflow_path": ["execution"],
    }


def link_prediction_stage(state: AgentState) -> Dict[str, Any]:
    """Complete sparse relations from observed temporal/place/person evidence."""
    print("\n[STAGE] Link Prediction")

    result = predict_sparse_relations(state)
    predictions = result.get("predictions", [])

    predicted_triples = [
        (prediction["head"], prediction["relation"], prediction["tail"])
        for prediction in predictions
    ]
    confidences = [prediction["confidence"] for prediction in predictions]

    print(f"  Target relation: {result.get('target_relation')}")
    print(f"  Predictions: {len(predicted_triples)} triples")

    return {
        "target_relation": result.get("target_relation") or state.get("target_relation"),
        "predicted_triples": predicted_triples,
        "prediction_confidence": confidences,
        "prediction_evidence": predictions,
        "link_prediction_done": True,
        "sparql_query": None,
        "sparql_results": None,
        "result_verification": None,
        "workflow_path": ["link_prediction"],
    }


def answer_generation_stage(state: AgentState) -> Dict[str, Any]:
    """Generate the final user-facing answer."""
    print("\n[STAGE] Answer Generation")

    system_prompt, user_prompt = build_answer_generation_prompt(state)

    answer = call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.5,
    )

    sources = collect_answer_sources(state.get("sparql_results") or [])

    print(f"  Answer generated ({len(answer)} chars)")

    return {
        "answer": answer,
        "sources": sources,
        "workflow_path": ["answer_generation"],
    }


def build_answer_generation_prompt(state: AgentState) -> tuple[str, str]:
    """Build the exact prompt used by the final answer stage."""
    from app.prompts.answer_generation import (
        ANSWER_GENERATION_SYSTEM,
        ANSWER_GENERATION_USER_TEMPLATE,
        format_link_prediction_for_prompt,
        format_results_for_prompt,
    )

    results_text = format_results_for_prompt(state.get("sparql_results") or [])
    link_pred_info = format_link_prediction_for_prompt(
        state.get("predicted_triples", []),
        state.get("prediction_confidence", []),
        state.get("prediction_evidence", []),
    )

    user_prompt = ANSWER_GENERATION_USER_TEMPLATE.format(
        query=state["query"],
        sparql_query=state.get("sparql_query", "없음"),
        results=results_text,
        link_prediction_info=link_pred_info,
    )

    return ANSWER_GENERATION_SYSTEM, user_prompt


def collect_answer_sources(results: list[Dict[str, Any]]) -> list[str]:
    """Collect compact source ids from SPARQL result values."""
    sources = []
    for result in results:
        for value in result.values():
            if "data/" in str(value):
                event_id = str(value).split("/")[-1]
                if event_id not in sources:
                    sources.append(event_id)
    return sources


def _parse_json_safe(text: str) -> Dict[str, Any]:
    """Parse a JSON object from an LLM response."""
    try:
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception:
        pass
    return {}


def _none_if_null(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "없음", "n/a"}:
        return None
    return text


def _build_time_constraint(time_word: Optional[str]) -> Optional[Dict[str, Any]]:
    if not time_word:
        return None

    time_map = {
        "어제": -1,
        "그제": -2,
        "최근": -7,
        "지난주": -7,
    }
    days_ago = time_map.get(time_word, -7)
    target_date = datetime.now() + timedelta(days=days_ago)
    return {
        "word": time_word,
        "date": target_date.date().isoformat(),
        "start_datetime": target_date.replace(hour=0, minute=0).isoformat(),
    }


def _infer_intent_from_query(query: str) -> str:
    normalized = query.lower()
    if any(word in normalized for word in ["가능성", "가능성이", "연결", "통화하고 나서", "준비할 때"]):
        return "sparse_completion"
    if "사진" in normalized:
        return "photos_at_place"
    if "앱" in normalized:
        return "most_used_app"
    if "방문" in normalized or "들른" in normalized:
        return "visited_places"
    if "통화" in normalized:
        return "recent_calls"
    return "unknown"


def _infer_target_relation_from_query(query: str) -> Optional[str]:
    normalized = query.lower()
    if any(word in normalized for word in ["사진", "photo", "콘텐츠", "찍은"]):
        return "relatedEvent"
    if any(word in normalized for word in ["앱", "app", "notion", "slack", "gmail"]):
        return "usedDuring"
    if any(word in normalized for word in ["누구", "만났", "만난", "met"]):
        return "metDuring"
    if any(word in normalized for word in ["통화", "call"]) and any(
        word in normalized for word in ["후", "뒤", "나서", "after"]
    ):
        return "visitedAfter"
    return None


def _extract_person_mention(query: str) -> Optional[str]:
    english = re.search(r"[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+)+", query)
    if english:
        return english.group(0).strip()

    for name in ["김철수", "최대한", "이영희", "박민지", "정수진", "철수", "수진"]:
        if name in query:
            return name
    return None


def _extract_place_type(query: str) -> Optional[str]:
    normalized = query.lower()
    if "카페" in normalized or "cafe" in normalized or "스타벅스" in normalized or "투썸" in normalized:
        return "cafe"
    if "식당" in normalized or "음식점" in normalized or "restaurant" in normalized:
        return "restaurant"
    if "회사" in normalized or "오피스" in normalized or "office" in normalized:
        return "office"
    return None


def _normalize_place_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"카페", "cafe"}:
        return "cafe"
    if normalized in {"식당", "음식점", "restaurant"}:
        return "restaurant"
    if normalized in {"회사", "오피스", "office"}:
        return "office"
    return value


def _extract_place_mention(query: str) -> Optional[str]:
    for keyword in ["스타벅스", "투썸플레이스", "투썸", "샐러디", "맥도날드"]:
        if keyword in query:
            return keyword
    return None


def _extract_event_title(query: str) -> Optional[str]:
    for title in ["디자인 리뷰", "제품 기획 회의", "전체 회의", "1:1 미팅"]:
        if title in query:
            return title
    if "디자인" in query and "리뷰" in query:
        return "디자인 리뷰"
    return None


def _format_entities_for_sparql_prompt(state: AgentState) -> str:
    entities = state.get("entities", {})
    resolved = state.get("resolved_entities", {})
    parts = []

    person_info = resolved.get("person")
    if isinstance(person_info, dict):
        label = person_info.get("label", "")
        search_name = person_info.get("search_name", label)
        parts.append(f"person: {label} (search_name: {search_name})")
    elif entities.get("person"):
        parts.append(f"person: {entities['person']}")

    place_info = resolved.get("place")
    if isinstance(place_info, list) and place_info:
        labels = [place.get("label", "") for place in place_info[:3] if place.get("label")]
        if labels:
            parts.append(f"place: {', '.join(labels)}")
    elif entities.get("place_mention"):
        parts.append(f"place: {entities['place_mention']}")
    elif entities.get("place_type"):
        parts.append(f"place_type: {entities['place_type']}")

    if entities.get("event_title"):
        parts.append(f"event_title: {entities['event_title']}")
    if state.get("target_relation"):
        parts.append(f"target_relation: {state['target_relation']}")

    return "; ".join(parts) if parts else "없음"


def _format_time_info(time_constraint: Optional[Dict[str, Any]]) -> str:
    if not time_constraint:
        return "없음"
    return f"{time_constraint['word']} ({time_constraint['date']} 이후)"
