"""
Rule-based supervisor for the KG agent workflow.

The supervisor decides the next stage from the current state and produces a
short user-facing reason that can be streamed before the stage runs.
"""

from typing import Any, Dict, Tuple


STAGE_LABELS = {
    "query_analysis": "질의 분석",
    "entity_resolution": "엔티티 추출",
    "sparql_generation": "SPARQL 생성",
    "execution": "쿼리 실행",
    "link_prediction": "링크 예측",
    "answer": "답변 생성",
    "END": "완료",
}

MAX_SPARQL_RETRY = 2
MAX_TOTAL_ITERATIONS = 8


def supervisor_decide(state: Dict[str, Any]) -> Tuple[str, str]:
    """Return the next stage and a short explanation."""
    entities = state.get("entities", {}) or {}
    resolved_entities = state.get("resolved_entities", {}) or {}
    sparql_query = state.get("sparql_query")
    sparql_results = state.get("sparql_results")
    result_verification = state.get("result_verification")
    link_prediction_done = state.get("link_prediction_done", False)
    use_link_prediction = state.get("use_link_prediction", False)
    sparql_retry_count = state.get("sparql_retry_count", 0)
    error = state.get("error")

    if error and "[ERROR]" in str(error):
        return ("END", f"오류가 발생했습니다: `{str(error)[:80]}`\n작업을 종료합니다.")

    has_person = bool(entities.get("person"))
    has_place = bool(entities.get("place_type") or entities.get("place_mention"))
    person_resolved = bool(resolved_entities.get("person")) or not has_person
    place_resolved = ("place" in resolved_entities) or not has_place

    if (has_person or has_place) and not (person_resolved and place_resolved):
        parts = []
        if has_person and not person_resolved:
            parts.append(f"**{entities['person']}**")
        if has_place and not place_resolved:
            place_text = entities.get("place_mention") or entities.get("place_type")
            parts.append(f"장소 **{place_text}**")
        return (
            "entity_resolution",
            f"질의에서 {', '.join(parts)}을(를) 발견했으므로 다음은 `엔티티를 추출`합니다.",
        )

    if not sparql_query:
        if sparql_retry_count >= MAX_SPARQL_RETRY:
            return (
                "answer",
                f"SPARQL 생성을 {sparql_retry_count}회 시도했습니다. 현재까지의 정보로 `최종 답변을 생성`합니다.",
            )

        entity_desc = _describe_resolved_entities(resolved_entities)
        if entity_desc:
            reasoning = f"{entity_desc}이(가) 확인되었으므로 다음은 `SPARQL 쿼리를 생성`합니다."
        else:
            reasoning = "질의 분석이 완료되었으므로 다음은 `SPARQL 쿼리를 생성`합니다."
        return ("sparql_generation", reasoning)

    if sparql_query and sparql_results is None:
        return ("execution", "SPARQL 쿼리가 준비되었으므로 다음은 `쿼리를 실행`합니다.")

    if sparql_results is not None:
        count = len(sparql_results)

        if result_verification and result_verification.get("issue") in ("empty", "sparse"):
            if use_link_prediction and not link_prediction_done:
                issue = result_verification["issue"]
                if issue == "empty":
                    reasoning = "쿼리 결과가 비어있습니다. `링크 예측`으로 누락된 관계를 보강합니다."
                else:
                    reasoning = f"쿼리 결과가 {count}건으로 부족합니다. `링크 예측`으로 누락된 관계를 보강합니다."
                return ("link_prediction", reasoning)

            if link_prediction_done and sparql_retry_count < MAX_SPARQL_RETRY:
                return (
                    "sparql_generation",
                    "링크 예측 결과를 바탕으로 `SPARQL 쿼리를 생성`합니다.",
                )

        if count > 0:
            if link_prediction_done:
                reasoning = f"링크 예측 기반 쿼리 결과 {count}건을 확인했습니다. 다음은 `최종 답변을 생성`합니다."
            else:
                reasoning = f"쿼리 결과 {count}건을 확인했습니다. 다음은 `최종 답변을 생성`합니다."
        else:
            if link_prediction_done:
                reasoning = "링크 예측 결과도 없습니다. 현재까지의 정보를 바탕으로 `최종 답변을 생성`합니다."
            else:
                reasoning = "쿼리 결과가 없습니다. 현재까지의 정보를 바탕으로 `최종 답변을 생성`합니다."
        return ("answer", reasoning)

    return ("answer", "모든 단계가 완료되었습니다. `최종 답변을 생성`합니다.")


def _describe_resolved_entities(resolved: Dict[str, Any]) -> str:
    parts = []
    person = resolved.get("person")
    if isinstance(person, dict):
        label = person.get("label") or person.get("search_name")
        if label:
            parts.append(f"**{label}**")
    elif person:
        parts.append(f"**{person}**")

    place = resolved.get("place")
    if isinstance(place, list) and place:
        label = place[0].get("label")
        if label:
            parts.append(f"장소 **{label}**")

    return ", ".join(parts)


def format_reasoning_for_display(reasoning: str, stage_index: int) -> str:
    return f"**[{stage_index}단계]** {reasoning}"
