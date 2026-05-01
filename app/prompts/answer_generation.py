"""
Answer generation prompt templates.
"""

from typing import Any, Dict, List


ANSWER_GENERATION_SYSTEM = """당신은 스마트폰 로그 데이터를 읽어주는 개인 비서입니다.
SPARQL 실행 결과를 사용자에게 자연스럽고 따뜻한 한국어로 설명하세요.

원칙:
1. 제목이나 "답변:" 같은 접두어로 시작하지 마세요.
2. 사람 이름, 핵심 시간, 장소, 앱, 결론은 Markdown bold(`**...**`)로 강조하세요.
3. link prediction으로 보강된 내용은 반드시 문장 앞에 `[예측]`을 붙이고, 관측 fact처럼 단정하지 마세요.
4. confidence와 근거가 있으면 짧게 함께 설명하세요.
5. 너무 딱딱한 보고서체 대신 개인 비서가 알려주는 말투로 답하세요.
6. 마지막에는 사용자가 **직접 다시 물어볼 수 있는 구체적인 예시 질문** 한 문장만 덧붙이세요.
   예: "4월 17일 정수진과의 통화 기록도 궁금하시면 물어보세요."
   ⚠️ 주의: "찾아드릴게요", "확인해드릴게요" 같이 시스템이 알아서 조회하겠다는 표현은 절대 쓰지 마세요.
   사용자가 직접 새 질문을 입력해야 조회됩니다.
"""


ANSWER_GENERATION_USER_TEMPLATE = """# Original Query
{query}

# SPARQL Query
```sparql
{sparql_query}
```

# Query Results
{results}

# Link Prediction Info
{link_prediction_info}

# Instructions
위 결과를 바탕으로 사용자가 바로 이해할 수 있게 답하세요.
결과가 없으면 찾지 못했다고 솔직히 말하고, 다음에 확인할 수 있는 방향을 짧게 제안하세요.
"""


def format_results_for_prompt(results: List[Dict[str, Any]]) -> str:
    """Format SPARQL results for the answer prompt."""
    if not results:
        return "결과 없음"

    lines = []
    for i, row in enumerate(results, 1):
        lines.append(f"결과 {i}:")
        for key, value in row.items():
            lines.append(f"  - {key}: {value}")
        lines.append("")

    return "\n".join(lines)


def format_link_prediction_for_prompt(
    predicted_triples: List[tuple],
    confidences: List[float],
    prediction_evidence: List[Dict[str, Any]] = None,
) -> str:
    """Format request-scoped predicted triples and evidence."""
    if not predicted_triples:
        return "사용하지 않음"

    evidence_by_triple = {
        (item.get("head"), item.get("relation"), item.get("tail")): item
        for item in (prediction_evidence or [])
        if isinstance(item, dict)
    }

    lines = [
        "아래 관계는 KG에 영구 저장된 fact가 아니라 이번 요청에서만 사용한 예측 관계입니다.",
        "답변에서는 반드시 `[예측]`으로 표시하세요.",
    ]
    for index, triple in enumerate(predicted_triples):
        head, relation, tail = triple
        evidence = evidence_by_triple.get((head, relation, tail), {})
        confidence = evidence.get("confidence")
        if confidence is None and index < len(confidences):
            confidence = confidences[index]
        evidence_text = evidence.get("evidence", "근거 없음")
        lines.append(
            f"- ({head}) -[{relation}]-> ({tail}) "
            f"[confidence: {float(confidence or 0):.2f}] evidence: {evidence_text}"
        )

    return "\n".join(lines)
