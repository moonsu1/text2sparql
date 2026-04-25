"""
Supervisor: 다음 실행 Stage 결정 + Reasoning 생성

Rule-based supervisor (LLM 불필요 → 즉시 결정, 빠르고 안정적)
각 단계의 State를 보고 다음에 무엇을 해야 할지 결정하고
그 이유를 한국어 reasoning으로 출력합니다.
"""

from typing import Tuple, Dict, Any


# Stage 이름 → 사람이 읽기 좋은 표현
STAGE_LABELS = {
    "query_analysis": "질의 분석",
    "entity_resolution": "엔티티 추출",
    "sparql_generation": "SPARQL 생성",
    "execution": "쿼리 실행",
    "link_prediction": "링크 예측",
    "answer": "답변 생성",
    "END": "완료",
}

# 무한루프 방지 최대 반복 횟수
MAX_SPARQL_RETRY = 2
MAX_TOTAL_ITERATIONS = 8


def supervisor_decide(state: Dict[str, Any]) -> Tuple[str, str]:
    """
    현재 State를 보고 다음 Stage와 Reasoning을 결정합니다.
    
    Returns:
        (next_stage: str, reasoning: str)
        
        next_stage 후보:
            "entity_resolution"   - 엔티티 추출 필요
            "sparql_generation"   - SPARQL 생성 필요
            "execution"           - SPARQL 실행 필요
            "link_prediction"     - Link prediction 필요
            "answer"              - 답변 생성 가능
            "END"                 - 작업 완료 또는 오류 종료
    """
    query = state.get("query", "")
    entities = state.get("entities", {})
    resolved_entities = state.get("resolved_entities", {})
    sparql_query = state.get("sparql_query")
    sparql_results = state.get("sparql_results")
    result_verification = state.get("result_verification")
    link_prediction_done = state.get("link_prediction_done", False)
    use_link_prediction = state.get("use_link_prediction", False)
    sparql_retry_count = state.get("sparql_retry_count", 0)
    error = state.get("error")
    
    # ── 오류 상태 종료 ──────────────────────────────────────
    if error and "[ERROR]" in str(error):
        reasoning = f"오류가 발생했습니다: `{error[:80]}`\n작업을 종료합니다."
        return ("END", reasoning)
    
    # ── 엔티티 추출 필요? ────────────────────────────────────
    # person 또는 place_type이 entities에 있지만 아직 resolved 안 된 경우
    has_person = bool(entities.get("person"))
    has_place = bool(entities.get("place_type"))
    person_resolved = bool(resolved_entities.get("person"))
    place_resolved = bool(resolved_entities.get("place")) or not has_place
    
    if (has_person or has_place) and not (person_resolved and place_resolved):
        parts = []
        if has_person and not person_resolved:
            parts.append(f"**{entities['person']}**")
        if has_place and not place_resolved:
            parts.append(f"장소 유형 **{entities['place_type']}**")
        
        entity_str = ", ".join(parts)
        reasoning = f"질의에서 {entity_str}을(를) 발견했으므로 다음은 `엔티티를 추출`합니다."
        return ("entity_resolution", reasoning)
    
    # ── SPARQL 생성 필요? ────────────────────────────────────
    if not sparql_query:
        if sparql_retry_count >= MAX_SPARQL_RETRY:
            reasoning = (
                f"SPARQL 생성을 {sparql_retry_count}회 시도했으나 유효한 결과를 얻지 못했습니다. "
                "현재까지의 정보로 답변을 생성합니다."
            )
            return ("answer", reasoning)
        
        entity_desc = _describe_resolved_entities(resolved_entities)
        if entity_desc:
            reasoning = f"{entity_desc}이(가) 확인되었으므로 다음은 `SPARQL 쿼리를 생성`합니다."
        else:
            reasoning = "질의 분석이 완료되었으므로 다음은 `SPARQL 쿼리를 생성`합니다."
        return ("sparql_generation", reasoning)
    
    # ── SPARQL 실행 필요? ────────────────────────────────────
    if sparql_query and sparql_results is None:
        reasoning = "SPARQL 쿼리가 준비되었으므로 다음은 `쿼리를 실행`합니다."
        return ("execution", reasoning)
    
    # ── 실행 후 결과 검증 ─────────────────────────────────────
    if sparql_results is not None:
        count = len(sparql_results)
        
        # Link prediction이 필요한 경우?
        if result_verification and result_verification.get("issue") in ("empty", "sparse"):
            if use_link_prediction and not link_prediction_done:
                issue = result_verification["issue"]
                if issue == "empty":
                    reasoning = (
                        f"쿼리 결과가 비어있습니다. "
                        "`링크 예측`으로 누락된 관계를 보강합니다."
                    )
                else:
                    reasoning = (
                        f"쿼리 결과가 {count}건으로 부족합니다. "
                        "`링크 예측`으로 데이터를 보강합니다."
                    )
                return ("link_prediction", reasoning)
            
            # Link prediction 완료 후 또는 미사용인 경우 → SPARQL 재시도 or 답변
            if link_prediction_done and sparql_retry_count < MAX_SPARQL_RETRY:
                reasoning = (
                    f"링크 예측으로 관계를 보강했습니다. "
                    "보강된 데이터로 `SPARQL 쿼리를 재생성`합니다."
                )
                return ("sparql_generation", reasoning)
        
        # 결과가 충분하거나 더 이상 시도할 방법이 없으면 → 답변 생성
        if count > 0:
            reasoning = (
                f"쿼리 결과 {count}건을 확인했습니다. "
                "다음은 `최종 답변을 생성`합니다."
            )
        else:
            reasoning = (
                "쿼리 결과가 없습니다. "
                "현재까지의 정보를 바탕으로 `최종 답변을 생성`합니다."
            )
        return ("answer", reasoning)
    
    # ── 기본: 답변으로 이동 ───────────────────────────────────
    reasoning = "모든 단계가 완료되었습니다. `최종 답변을 생성`합니다."
    return ("answer", reasoning)


# ── 헬퍼 함수 ──────────────────────────────────────────────

def _describe_resolved_entities(resolved: Dict[str, str]) -> str:
    """resolved_entities를 사람이 읽기 좋은 문자열로 변환"""
    parts = []
    if resolved.get("person"):
        label = resolved["person"].get("label", resolved["person"]) if isinstance(resolved["person"], dict) else str(resolved["person"])
        parts.append(f"**{label}**")
    if resolved.get("place"):
        label = resolved["place"][0].get("label", "") if isinstance(resolved.get("place"), list) and resolved["place"] else ""
        if label:
            parts.append(f"장소 **{label}**")
    return ", ".join(parts)


def format_reasoning_for_display(reasoning: str, stage_index: int) -> str:
    """
    Supervisor reasoning을 사용자에게 보여줄 형태로 포맷팅
    
    Args:
        reasoning: 원본 reasoning 텍스트
        stage_index: 몇 번째 판단인지 (1부터)
    
    Returns:
        포맷팅된 문자열
    """
    return f"**[{stage_index}단계]** {reasoning}"
