"""
SPARQL Generation Tools
SPARQL 생성 및 검증 도구
"""

import sys
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from app.agents.llm_client import call_llm
from app.prompts.text2sparql import (
    TEXT2SPARQL_SYSTEM,
    TEXT2SPARQL_USER_TEMPLATE,
    format_properties_for_prompt
)
from app.config import ONTOLOGY_DIR


def generate_sparql(
    query: str,
    intent: str,
    entities_text: str,
    time_info: str,
    predicted_triples: list = None
) -> str:
    """
    LLM을 이용해 SPARQL 쿼리 생성
    
    Args:
        query: 사용자 원본 질의
        intent: 질의 의도
        entities_text: 엔티티 정보 문자열
        time_info: 시간 제약 정보
        predicted_triples: Link prediction 결과 (선택)
    
    Returns:
        SPARQL 쿼리 문자열
    """
    catalog_path = ONTOLOGY_DIR / "property_catalog.yaml"
    with open(catalog_path, "r", encoding="utf-8") as f:
        property_catalog = yaml.safe_load(f)
    
    properties_text = format_properties_for_prompt(list(property_catalog.values()))
    
    additional_context = ""
    if predicted_triples:
        additional_context = "예측된 관계 (Link Prediction):\n"
        for triple in predicted_triples:
            additional_context += f"  - {triple}\n"
    
    system_prompt = TEXT2SPARQL_SYSTEM.format(properties=properties_text)
    user_prompt = TEXT2SPARQL_USER_TEMPLATE.format(
        query=query,
        intent=intent or "unknown",
        time_info=time_info or "없음",
        entities=entities_text or "없음",
        additional_context=additional_context or "없음"
    )
    
    sparql_result = call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1
    )
    
    sparql_query = _extract_sparql(sparql_result)
    sparql_query = _fix_label_search(sparql_query)
    
    print(f"  [SPARQLTool] SPARQL 생성 완료 ({len(sparql_query)} chars)")
    return sparql_query


def _extract_sparql(llm_output: str) -> str:
    """LLM 출력에서 SPARQL 쿼리 추출"""
    sparql_match = re.search(r'```sparql\s*(.*?)\s*```', llm_output, re.DOTALL)
    if sparql_match:
        return sparql_match.group(1).strip()
    
    prefix_match = re.search(r'(PREFIX.*)', llm_output, re.DOTALL)
    if prefix_match:
        return prefix_match.group(1).strip()
    
    return llm_output.strip()


def _fix_label_search(sparql: str) -> str:
    """rdfs:label "literal" 패턴을 FILTER(CONTAINS())로 변환"""
    pattern = r'(\?\w+)\s+rdfs:label\s+"([^"]+)"\s*\.?'
    
    matches = list(re.finditer(pattern, sparql))
    if matches:
        print(f"  [SPARQLTool] {len(matches)}개 rdfs:label 패턴 → CONTAINS 변환")
        for match in reversed(matches):
            var = match.group(1)
            literal = match.group(2)
            name_var = f"{var}Name"
            start, end = match.span()
            replacement = f'{var} rdfs:label {name_var} .\n  FILTER(CONTAINS({name_var}, "{literal}"))'
            sparql = sparql[:start] + replacement + sparql[end:]
    
    return sparql


def verify_sparql_syntax(sparql: str) -> Dict[str, Any]:
    """
    SPARQL 구문 검증
    
    Args:
        sparql: 검증할 SPARQL 쿼리
    
    Returns:
        {"is_valid": bool, "error": str or None}
    """
    if not sparql or not sparql.strip():
        return {"is_valid": False, "error": "빈 SPARQL 쿼리"}
    
    # 기본 구조 검증
    sparql_upper = sparql.upper()
    
    if "SELECT" not in sparql_upper and "ASK" not in sparql_upper and "CONSTRUCT" not in sparql_upper:
        return {"is_valid": False, "error": "SELECT/ASK/CONSTRUCT 키워드 없음"}
    
    if "WHERE" not in sparql_upper:
        return {"is_valid": False, "error": "WHERE 절 없음"}
    
    # 중괄호 매칭
    open_count = sparql.count("{")
    close_count = sparql.count("}")
    if open_count != close_count:
        return {
            "is_valid": False,
            "error": f"중괄호 불일치 ({{ {open_count}개, }} {close_count}개)"
        }
    
    return {"is_valid": True, "error": None}
