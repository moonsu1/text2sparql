"""
Answer Generation Prompt Templates
SPARQL 실행 결과를 자연어로 설명하는 프롬프트
"""

from typing import List, Dict

ANSWER_GENERATION_SYSTEM = """당신은 스마트폰 로그 데이터 분석 전문가입니다.
SPARQL 쿼리 실행 결과를 사용자에게 자연스럽고 이해하기 쉽게 설명하세요.
말투는 딱딱한 보고서체가 아니라, 개인 비서가 차분하게 알려주는 듯한 따뜻한 한국어로 작성하세요.

# 답변 원칙

1. 간결하고 명확하게 설명
2. 구체적인 정보 포함 (이름, 시간, 장소 등)
3. 시간은 "04월 21일 10시 35분" 형식으로 표현
4. 사람 이름, 가장 중요한 날짜/시간, 장소, 핵심 결론은 Markdown bold(`**...**`)로 강조
5. Link prediction으로 예측된 내용이 있으면 "[예측]" 표시
6. 제목이나 "답변:" 접두어로 시작하지 말 것
7. 마지막에는 결과와 자연스럽게 이어지는 짧은 추천 질문을 한 문장으로 덧붙일 것
8. 근거가 있으면 마지막 또는 마지막 직전에 짧게 명시

# 예시

좋은 답변:
"**김철수님**과는 **04월 21일 10시 35분**에 통화하셨어요.
이후 **11시 30분**에는 **스타벅스 역삼점**에 방문한 기록이 있습니다.

근거: call_005, visit_007
원하시면 이 일정 전후의 통화나 방문 기록도 같이 정리해드릴까요?"

나쁜 답변:
"CallEvent가 1개 있고 VisitEvent가 1개 있습니다."
"""

ANSWER_GENERATION_USER_TEMPLATE = """# Original Query
{query}

# SPARQL Query
```sparql
{sparql_query}
```

# Query Results
{results}

# Link Prediction Info (if used)
{link_prediction_info}

# Instructions
위 결과를 바탕으로 사용자에게 자연스러운 답변을 생성하세요.
결과가 없으면 "해당 정보를 찾을 수 없습니다"라고 답하세요.
"""


def format_results_for_prompt(results: List[Dict]) -> str:
    """SPARQL 결과를 프롬프트용으로 포맷"""
    if not results:
        return "결과 없음"
    
    lines = []
    for i, row in enumerate(results, 1):
        lines.append(f"결과 {i}:")
        for key, value in row.items():
            lines.append(f"  - {key}: {value}")
        lines.append("")
    
    return "\n".join(lines)


def format_link_prediction_for_prompt(predicted_triples: List[tuple], 
                                      confidences: List[float]) -> str:
    """Link prediction 결과를 프롬프트용으로 포맷"""
    if not predicted_triples:
        return "Link prediction 사용 안 함"
    
    lines = ["예측된 관계:"]
    for triple, conf in zip(predicted_triples, confidences):
        head, rel, tail = triple
        lines.append(f"  - ({head}) -[{rel}]-> ({tail}) [신뢰도: {conf:.2f}]")
    
    return "\n".join(lines)
