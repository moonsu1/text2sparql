"""
Supervisor Stage Nodes
각 Stage의 실제 로직 구현

각 stage는 focused tools만 사용하므로 Gemini Flash도 안정적으로 처리합니다.
"""

import sys
import re
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.agents.state import AgentState
from app.agents.llm_client import call_llm
from app.agents.tools.entity_tools import (
    resolve_person_entity,
    resolve_place_entity,
    resolve_korean_name,
)
from app.agents.tools.sparql_tools import generate_sparql, verify_sparql_syntax
from app.agents.tools.execution_tools import execute_sparql_on_fuseki, verify_results_quality
from app.agents.tools.link_prediction_tools import predict_missing_links_for_person


# ═══════════════════════════════════════════════════════
# Stage 0: Query Analysis
# ═══════════════════════════════════════════════════════

def query_analysis_stage(state: AgentState) -> Dict[str, Any]:
    """
    Stage 0: 사용자 질의 분석
    - intent, entities, time_constraint 추출
    - 기존 query_analysis_node 로직과 동일
    """
    print("\n[STAGE] Query Analysis")
    
    query = state["query"]
    
    analysis_prompt = f"""다음 질문을 분석하세요:

질문: "{query}"

다음 정보를 JSON 형식으로 추출하세요:
1. intent: 질문의 의도 (recent_calls, most_used_app, visited_places, call_after_cafe, meeting_location, photos_at_place 중 하나)
2. time_constraint: 시간 제약 (어제, 최근, 지난주 등, 없으면 null)
3. person_mention: 언급된 사람 이름 (없으면 null)
4. place_type: 언급된 장소 유형 (카페, 식당, 회사 등, 없으면 null)

JSON 형식으로만 답하세요:
{{
  "intent": "...",
  "time_constraint": "...",
  "person_mention": "...",
  "place_type": "..."
}}"""
    
    result = call_llm(
        system_prompt="당신은 질의 분석 전문가입니다.",
        user_prompt=analysis_prompt,
        temperature=0.1
    )
    
    # JSON 파싱
    analysis = _parse_json_safe(result)
    
    intent = analysis.get("intent")
    person_mention = analysis.get("person_mention")
    
    # 한글 이름 → 영어 변환
    if person_mention:
        eng_name = resolve_korean_name(person_mention)
        if eng_name != person_mention:
            print(f"  [Analysis] 이름 변환: {person_mention} → {eng_name}")
            person_mention = eng_name
    
    entities = {
        "person": person_mention,
        "place_type": analysis.get("place_type")
    }
    
    # 시간 제약 처리
    time_constraint = None
    time_word = analysis.get("time_constraint")
    if time_word and time_word != "null":
        time_map = {"어제": -1, "그제": -2, "최근": -7, "지난주": -7}
        days_ago = time_map.get(time_word, -7)
        target_date = datetime.now() + timedelta(days=days_ago)
        time_constraint = {
            "word": time_word,
            "date": target_date.date().isoformat(),
            "start_datetime": target_date.replace(hour=0, minute=0).isoformat()
        }
    
    print(f"  Intent: {intent}")
    print(f"  Entities: {entities}")
    print(f"  Time: {time_constraint}")
    
    return {
        "intent": intent,
        "entities": entities,
        "time_constraint": time_constraint,
        "workflow_path": ["query_analysis"],
        "resolved_entities": {},
        "sparql_results": None,
        "link_prediction_done": False,
        "sparql_retry_count": 0,
    }


# ═══════════════════════════════════════════════════════
# Stage 1: Entity Resolution
# ═══════════════════════════════════════════════════════

def entity_resolution_stage(state: AgentState) -> Dict[str, Any]:
    """
    Stage 1: 엔티티 추출 (Entity Resolution)
    - Person URI 해결
    - Place URI 해결
    Tools: resolve_person_entity, resolve_place_entity
    """
    print("\n[STAGE] Entity Resolution")
    
    entities = state.get("entities", {})
    resolved = dict(state.get("resolved_entities", {}))
    
    person_name = entities.get("person")
    place_type = entities.get("place_type")
    
    # Person 해결
    if person_name and not resolved.get("person"):
        person_result = resolve_person_entity(person_name)
        if person_result:
            resolved["person"] = person_result
            print(f"  Person 해결: {person_result.get('label')} ({person_result.get('uri', '')[:40]})")
        else:
            print(f"  Person '{person_name}' 해결 실패 → 이름 그대로 사용")
            resolved["person"] = {"uri": None, "label": person_name, "search_name": person_name}
    
    # Place 해결
    if place_type and not resolved.get("place"):
        place_results = resolve_place_entity(place_type)
        if place_results:
            resolved["place"] = place_results
            labels = [p.get("label", "") for p in place_results[:2]]
            print(f"  Place 해결: {labels}")
        else:
            print(f"  Place '{place_type}' 해결 실패")
            resolved["place"] = []
    
    return {
        "resolved_entities": resolved,
        "workflow_path": ["entity_resolution"],
    }


# ═══════════════════════════════════════════════════════
# Stage 2: SPARQL Generation
# ═══════════════════════════════════════════════════════

def sparql_generation_stage(state: AgentState) -> Dict[str, Any]:
    """
    Stage 2: SPARQL 쿼리 생성
    - LLM으로 SPARQL 생성
    - 구문 검증
    Tools: generate_sparql, verify_sparql_syntax
    """
    print("\n[STAGE] SPARQL Generation")
    
    query = state["query"]
    intent = state.get("intent", "unknown")
    entities = state.get("entities", {})
    resolved = state.get("resolved_entities", {})
    time_constraint = state.get("time_constraint")
    predicted_triples = state.get("predicted_triples", [])
    sparql_retry_count = state.get("sparql_retry_count", 0)
    
    # 엔티티 텍스트 조합 (resolved URI + label 정보 포함)
    entity_parts = []
    
    person_info = resolved.get("person")
    if person_info:
        if isinstance(person_info, dict):
            label = person_info.get("label", "")
            search_name = person_info.get("search_name", label)
            entity_parts.append(f"person: {label} (search_name: {search_name})")
        else:
            entity_parts.append(f"person: {person_info}")
    elif entities.get("person"):
        entity_parts.append(f"person: {entities['person']}")
    
    place_info = resolved.get("place")
    if place_info and isinstance(place_info, list) and place_info:
        labels = [p.get("label", "") for p in place_info[:2]]
        entity_parts.append(f"place: {', '.join(labels)}")
    elif entities.get("place_type"):
        entity_parts.append(f"place_type: {entities['place_type']}")
    
    entities_text = "; ".join(entity_parts) if entity_parts else "없음"
    
    # 시간 정보
    time_info = "없음"
    if time_constraint:
        time_info = f"{time_constraint['word']} ({time_constraint['date']} 이후)"
    
    # SPARQL 생성
    sparql_query = generate_sparql(
        query=query,
        intent=intent,
        entities_text=entities_text,
        time_info=time_info,
        predicted_triples=predicted_triples if predicted_triples else None
    )
    
    # 구문 검증
    validation = verify_sparql_syntax(sparql_query)
    if not validation["is_valid"]:
        print(f"  [WARNING] SPARQL 구문 오류: {validation['error']}")
    
    return {
        "sparql_query": sparql_query,
        "sparql_results": None,  # 새로운 SPARQL이므로 결과 초기화
        "result_verification": None,
        "sparql_retry_count": sparql_retry_count + 1,
        "workflow_path": ["sparql_generation"],
    }


# ═══════════════════════════════════════════════════════
# Stage 3: Execution
# ═══════════════════════════════════════════════════════

def execution_stage(state: AgentState) -> Dict[str, Any]:
    """
    Stage 3: SPARQL 실행 & 결과 검증
    Tools: execute_sparql_on_fuseki, verify_results_quality
    """
    print("\n[STAGE] Execution")
    
    sparql_query = state.get("sparql_query", "")
    
    if not sparql_query:
        return {
            "sparql_results": [],
            "execution_time_ms": 0.0,
            "result_verification": {"is_complete": False, "issue": "empty", "suggestion": "SPARQL 없음"},
            "error": "SPARQL 쿼리가 없습니다",
            "workflow_path": ["execution"],
        }
    
    # 실행
    exec_result = execute_sparql_on_fuseki(sparql_query)
    results = exec_result["results"]
    execution_time = exec_result["execution_time_ms"]
    
    # 결과 검증
    verification = verify_results_quality(results)
    
    print(f"  결과: {len(results)}건, 검증: {verification['issue']}")
    
    return {
        "sparql_results": results,
        "execution_time_ms": execution_time,
        "result_verification": verification,
        "workflow_path": ["execution"],
    }


# ═══════════════════════════════════════════════════════
# Stage 4: Link Prediction
# ═══════════════════════════════════════════════════════

def link_prediction_stage(state: AgentState) -> Dict[str, Any]:
    """
    Stage 4: Link Prediction (GCN+TransE)
    - Sparse data 보강
    Tools: predict_missing_links_for_person
    """
    print("\n[STAGE] Link Prediction")
    
    resolved = state.get("resolved_entities", {})
    entities = state.get("entities", {})
    
    # Person 이름 결정
    person_name = None
    person_info = resolved.get("person")
    if isinstance(person_info, dict):
        person_name = person_info.get("search_name") or person_info.get("label")
    elif entities.get("person"):
        person_name = entities["person"]
    
    predicted_triples = []
    confidences = []
    
    if person_name:
        raw_predictions = predict_missing_links_for_person(person_name)
        
        for head, tail, conf in raw_predictions:
            predicted_triples.append((head, "http://example.org/smartphone-log#visitedAfter", tail))
            confidences.append(conf)
        
        print(f"  예측 완료: {len(predicted_triples)}개 triple")
    else:
        print("  Person 정보 없음 → Link prediction 스킵")
    
    return {
        "predicted_triples": predicted_triples,
        "prediction_confidence": confidences,
        "link_prediction_done": True,
        "sparql_query": None,  # SPARQL 재생성을 위해 초기화
        "sparql_results": None,
        "result_verification": None,
        "workflow_path": ["link_prediction"],
    }


# ═══════════════════════════════════════════════════════
# Stage 5: Answer Generation
# ═══════════════════════════════════════════════════════

def answer_generation_stage(state: AgentState) -> Dict[str, Any]:
    """
    Stage 5: 최종 자연어 답변 생성
    - LLM으로 결과를 자연어로 변환
    """
    print("\n[STAGE] Answer Generation")
    
    from app.prompts.answer_generation import (
        ANSWER_GENERATION_SYSTEM,
        ANSWER_GENERATION_USER_TEMPLATE,
        format_results_for_prompt,
        format_link_prediction_for_prompt
    )
    
    results_text = format_results_for_prompt(state.get("sparql_results") or [])
    
    link_pred_info = format_link_prediction_for_prompt(
        state.get("predicted_triples", []),
        state.get("prediction_confidence", [])
    )
    
    user_prompt = ANSWER_GENERATION_USER_TEMPLATE.format(
        query=state["query"],
        sparql_query=state.get("sparql_query", "없음"),
        results=results_text,
        link_prediction_info=link_pred_info
    )
    
    answer = call_llm(
        system_prompt=ANSWER_GENERATION_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.5
    )
    
    # Sources 추출
    sources = []
    for result in (state.get("sparql_results") or []):
        for key, value in result.items():
            if "data/" in str(value):
                event_id = str(value).split("/")[-1]
                if event_id not in sources:
                    sources.append(event_id)
    
    print(f"  답변 생성 완료 ({len(answer)} chars)")
    
    return {
        "answer": answer,
        "sources": sources,
        "workflow_path": ["answer_generation"],
    }


# ── 헬퍼 함수 ──────────────────────────────────────────

def _parse_json_safe(text: str) -> dict:
    """LLM 출력에서 JSON 안전하게 파싱"""
    try:
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception:
        pass
    return {}
