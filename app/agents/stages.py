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
from app.agents.tools.link_prediction_tools import (
    predict_sparse_relations,
    predict_second_hop,
    MULTIHOP_CHAINS,
)
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

    # Rule-based 2-hop 감지를 항상 먼저 시도 (LLM은 단일 관계만 알기 때문)
    _rule_relation = _infer_target_relation_from_query(query)
    if _rule_relation in MULTIHOP_CHAINS:
        # 2-hop 패턴이 감지되면 LLM 결과 무시하고 chain으로 결정
        target_relation = _rule_relation
    elif _llm_relation in LINK_PREDICTION_RELATIONS:
        target_relation = _llm_relation
    else:
        # LLM이 유효하지 않거나 null → rule-based 1-hop 결과 사용
        target_relation = _rule_relation

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
    # 멀티홉 체인인 경우: lp_chain에 체인 키 저장, target_relation은 1차 관계로 설정
    lp_chain = None
    if target_relation in MULTIHOP_CHAINS:
        lp_chain = target_relation
        first_relation = MULTIHOP_CHAINS[target_relation][0]
        target_relation = first_relation  # 1차 LP에 사용할 관계
        print(f"  [Analysis] 멀티홉 체인 감지: {lp_chain} → 1차={target_relation}")

    use_link_prediction = (
        target_relation in LINK_PREDICTION_RELATIONS
        or lp_chain in MULTIHOP_CHAINS
    ) if (target_relation or lp_chain) else False

    if use_link_prediction:
        label = f"chain={lp_chain}" if lp_chain else f"relation={target_relation}"
        print(f"  [Analysis] {label} → SPARQL 실행 후 결과 없으면 LP 대기")

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
        "lp_chain": lp_chain,
        "lp_hop_index": 0,
        "lp_intermediate_node": None,
    }


GENERIC_PLACE_TYPES = {"카페", "cafe", "식당", "restaurant", "음식점", "회사", "office", "편의점", "마트"}


def entity_resolution_stage(state: AgentState) -> Dict[str, Any]:
    """Resolve person and place mentions to KG entities when available.

    Place resolution 정책:
    - place_mention (구체적 장소명, e.g. "스타벅스") → KG 검색 후 SPARQL에 바인딩
    - place_type (범주적, e.g. "카페") → KG 검색하지 않음, SPARQL에서 타입 필터로 처리
      (카페 1000개를 모두 열거하면 오히려 노이즈, 타입 필터가 더 정확)
    """
    print("\n[STAGE] Entity Resolution")

    entities = state.get("entities", {})
    resolved = dict(state.get("resolved_entities", {}))

    person_name = entities.get("person")
    place_mention = entities.get("place_mention")  # 구체적 장소명만 추출
    place_type = entities.get("place_type")

    # ── Person 조회 ──────────────────────────────────────────────────────
    if person_name and not resolved.get("person"):
        person_result = resolve_person_entity(person_name)
        if person_result:
            resolved["person"] = person_result
            print(f"  Person resolved: {person_result.get('label')}")
        else:
            print(f"  Person '{person_name}' not found; using search text")
            resolved["person"] = {"uri": None, "label": person_name, "search_name": person_name}

    # ── Place 조회: 구체적 장소명이 있을 때만 KG 검색 ───────────────────
    if place_mention and not resolved.get("place"):
        # 구체적 장소명 ("스타벅스") → KG에서 매칭되는 URI 조회
        is_generic = place_mention.lower().strip() in GENERIC_PLACE_TYPES
        if not is_generic:
            place_results = resolve_place_entity(place_mention)
            if place_results:
                resolved["place"] = place_results
                labels = [p.get("label", "") for p in place_results[:2]]
                print(f"  Place resolved (specific): {labels}")
            else:
                print(f"  Place '{place_mention}' not found in KG")
                resolved["place"] = []
        else:
            print(f"  Place '{place_mention}' is generic type → KG 검색 생략, SPARQL 타입 필터 사용")
    elif place_type and not resolved.get("place"):
        # 범주만 있고 구체적 장소명 없음 → KG 검색 안 함 (타입 필터로 처리)
        # Supervisor가 "place 미해결" 루프에 빠지지 않도록 빈 리스트로 완료 표시
        resolved["place"] = []
        print(f"  Place type '{place_type}' → KG 검색 생략, SPARQL 타입 필터 사용")

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

    sparql_query, mermaid_graph = generate_sparql(
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
        "mermaid_graph": mermaid_graph,
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
    """Complete sparse relations from observed temporal/place/person evidence.

    멀티홉 체인인 경우:
    - lp_hop_index == 0: 1차 LP 수행, 결과 tail을 lp_intermediate_node에 저장
    - lp_hop_index == 1: lp_intermediate_node를 head로 2차 LP 수행, link_prediction_done=True
    """
    print("\n[STAGE] Link Prediction")

    lp_chain = state.get("lp_chain")
    lp_hop_index = state.get("lp_hop_index", 0)
    lp_intermediate_node = state.get("lp_intermediate_node")

    # ── 멀티홉 2차 hop ─────────────────────────────────────────────────
    if lp_chain and lp_hop_index == 1 and lp_intermediate_node:
        second_relation = MULTIHOP_CHAINS[lp_chain][1]
        print(f"  [2-hop] 2차 예측 시작: chain={lp_chain}, relation={second_relation}, head={lp_intermediate_node}")

        predictions = predict_second_hop(state, lp_intermediate_node, second_relation)
        predicted_triples = [
            (p["head"], p["relation"], p["tail"])
            for p in predictions
        ]
        confidences = [p["confidence"] for p in predictions]

        print(f"  [2-hop] 2차 예측 결과: {len(predicted_triples)}건")

        return {
            "predicted_triples": predicted_triples,
            "prediction_confidence": confidences,
            "prediction_evidence": predictions,
            "link_prediction_done": True,
            "lp_hop_index": 2,
            "sparql_query": None,
            "sparql_results": None,
            "result_verification": None,
            "workflow_path": ["link_prediction_hop2"],
        }

    # ── 1차 hop (1-hop 단일 관계 또는 멀티홉 1차) ─────────────────────
    result = predict_sparse_relations(state)
    predictions = result.get("predictions", [])

    predicted_triples = [
        (p["head"], p["relation"], p["tail"])
        for p in predictions
    ]
    confidences = [p["confidence"] for p in predictions]

    print(f"  Target relation: {result.get('target_relation')}")
    print(f"  Predictions: {len(predicted_triples)} triples")

    # 멀티홉 체인이면 1차 결과 tail을 저장하고 2차 hop 대기
    if lp_chain and predictions:
        intermediate_uri = predictions[0].get("tail", "")
        print(f"  [1-hop] 중간 노드 저장: {intermediate_uri} → 2차 LP 대기")
        return {
            "target_relation": result.get("target_relation") or state.get("target_relation"),
            "predicted_triples": predicted_triples,
            "prediction_confidence": confidences,
            "prediction_evidence": predictions,
            "link_prediction_done": False,   # 아직 완료 아님
            "lp_intermediate_node": intermediate_uri,
            "lp_hop_index": 1,               # 다음 호출에서 2차 실행
            "sparql_query": None,
            "sparql_results": None,
            "result_verification": None,
            "workflow_path": ["link_prediction_hop1"],
        }

    # 1-hop 단일 관계 (체인 없음) 또는 1차에서 예측 실패
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
    has_photo = any(word in normalized for word in ["사진", "photo", "콘텐츠", "찍은"])
    has_call_after = any(word in normalized for word in ["통화", "call"]) and any(
        word in normalized for word in ["후", "뒤", "나서", "after"]
    )
    has_who = any(word in normalized for word in ["누구", "만났", "만난", "met"])
    has_call = any(word in normalized for word in ["통화", "call"])

    # 2-hop 패턴 먼저 체크
    if has_photo and has_who:
        return "relatedEvent+metDuring"
    if has_call_after and has_who:
        return "visitedAfter+metDuring"
    if has_call_after and has_photo:
        return "visitedAfter+relatedEvent_rev"
    if has_photo and has_call and not has_call_after:
        return "relatedEvent+visitedAfter_rev"

    # 1-hop
    if has_photo:
        return "relatedEvent"
    if any(word in normalized for word in ["앱", "app", "notion", "slack", "gmail"]):
        return "usedDuring"
    if has_who:
        return "metDuring"
    if has_call_after:
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
        # KG에서 찾은 구체적 장소명 → SPARQL에서 CONTAINS로 바인딩
        labels = [place.get("label", "") for place in place_info[:3] if place.get("label")]
        if labels:
            parts.append(f"place (specific, use CONTAINS filter): {', '.join(labels)}")
    elif entities.get("place_mention"):
        # KG에서 못 찾았지만 사용자가 언급한 구체적 장소명
        parts.append(f"place (specific, use CONTAINS filter): {entities['place_mention']}")
    elif entities.get("place_type"):
        # 범주형 장소 타입 → SPARQL에서 타입 필터로 처리
        parts.append(f"place_type (use type filter, NOT specific label): {entities['place_type']}")

    if entities.get("event_title"):
        parts.append(f"event_title: {entities['event_title']}")
    if state.get("target_relation"):
        parts.append(f"target_relation: {state['target_relation']}")

    return "; ".join(parts) if parts else "없음"


def _format_time_info(time_constraint: Optional[Dict[str, Any]]) -> str:
    if not time_constraint:
        return "없음"
    return f"{time_constraint['word']} ({time_constraint['date']} 이후)"
