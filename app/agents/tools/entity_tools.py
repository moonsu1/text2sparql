"""
Entity Resolution Tools
Entity 추출 및 모호성 해결 도구
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from app.config import CONTACTS, FUSEKI_URL, FUSEKI_DATASET


# 한글 이름 → 영어 이름 매핑
NAME_MAPPING = {
    "김철수": "Kim Chul",
    "최대한": "Choi Dae",
    "이영희": "Lee Young",
    "박지민": "Park Ji",
    "정수현": "Jung Su",
    "철수": "Kim Chul",
    "영희": "Lee Young",
    "지민": "Park Ji",
    "수현": "Jung Su",
}


def resolve_korean_name(name: str) -> str:
    """한글 이름을 영어 부분 이름으로 변환"""
    if not name:
        return name
    for kor, eng in NAME_MAPPING.items():
        if kor in name:
            return eng
    return name


def search_person_in_fuseki(partial_name: str) -> List[Dict[str, str]]:
    """
    Fuseki에서 부분 이름 매칭으로 Person URI 검색
    
    Args:
        partial_name: 검색할 이름 (부분 매칭)
    
    Returns:
        [{"uri": str, "label": str}, ...]
    """
    try:
        from app.step3_load.fuseki_executor import FusekiSPARQLExecutor
        executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
        
        query = f"""
        PREFIX log: <http://example.org/smartphone-log#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?person ?label WHERE {{
            ?person a log:Person .
            ?person rdfs:label ?label .
            FILTER(CONTAINS(LCASE(?label), LCASE("{partial_name}")))
        }}
        LIMIT 5
        """
        
        results = executor.execute_query(query)
        return [{"uri": r.get("person", ""), "label": r.get("label", "")} for r in results]
    except Exception as e:
        print(f"  [EntityTool] Fuseki 검색 오류: {e}")
        return []


def check_entity_ambiguity(entity_name: str) -> Dict[str, Any]:
    """
    Entity 이름이 모호한지 확인 (여러 후보가 있는지)
    
    Args:
        entity_name: 확인할 이름
    
    Returns:
        {"is_ambiguous": bool, "candidates": List[dict], "resolved_name": str}
    """
    # 영어 이름으로 변환 시도
    eng_name = resolve_korean_name(entity_name)
    
    candidates = search_person_in_fuseki(eng_name)
    
    if not candidates and eng_name != entity_name:
        # 원래 이름으로도 검색
        candidates = search_person_in_fuseki(entity_name)
    
    is_ambiguous = len(candidates) > 1
    
    print(f"  [EntityTool] '{entity_name}' → '{eng_name}' 검색: {len(candidates)}개 후보")
    
    return {
        "is_ambiguous": is_ambiguous,
        "candidates": candidates,
        "resolved_name": eng_name,
        "original_name": entity_name
    }


def align_entity(entity_name: str, candidates: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """
    후보 중 가장 잘 맞는 Entity 선택
    
    Args:
        entity_name: 원래 이름
        candidates: [{"uri": str, "label": str}, ...]
    
    Returns:
        {"uri": str, "label": str} or None
    """
    if not candidates:
        return None
    
    if len(candidates) == 1:
        return candidates[0]
    
    # 이름 유사도로 최선 선택 (간단히 첫 번째)
    eng_name = resolve_korean_name(entity_name).lower()
    
    best = None
    best_score = -1
    for c in candidates:
        label = c.get("label", "").lower()
        # 간단한 포함 관계 점수
        score = 1 if eng_name in label else 0
        if score > best_score:
            best_score = score
            best = c
    
    return best or candidates[0]


def resolve_person_entity(person_name: str) -> Optional[Dict[str, str]]:
    """
    사람 이름에서 RDF URI + label 해결 (원스텝)
    
    Args:
        person_name: 한글 또는 영어 이름
    
    Returns:
        {"uri": str, "label": str, "search_name": str} or None
    """
    ambiguity_result = check_entity_ambiguity(person_name)
    candidates = ambiguity_result["candidates"]
    
    if not candidates:
        print(f"  [EntityTool] '{person_name}' 해당 Person 없음")
        return None
    
    best = align_entity(person_name, candidates)
    if best:
        best["search_name"] = ambiguity_result["resolved_name"]
    return best


def resolve_place_entity(place_type: str) -> List[Dict[str, str]]:
    """
    장소 유형에서 RDF URI 목록 해결
    
    Args:
        place_type: 장소 유형 (cafe, restaurant, office 등)
    
    Returns:
        [{"uri": str, "label": str, "type": str}, ...]
    """
    try:
        from app.step3_load.fuseki_executor import FusekiSPARQLExecutor
        executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
        
        query = f"""
        PREFIX log: <http://example.org/smartphone-log#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?place ?label ?type WHERE {{
            ?place a log:Place .
            ?place rdfs:label ?label .
            OPTIONAL {{ ?place log:placeType ?type . }}
            FILTER(CONTAINS(LCASE(?label), LCASE("{place_type}")) || 
                   CONTAINS(LCASE(STR(?type)), LCASE("{place_type}")))
        }}
        LIMIT 5
        """
        
        results = executor.execute_query(query)
        return [
            {"uri": r.get("place", ""), "label": r.get("label", ""), "type": r.get("type", "")}
            for r in results
        ]
    except Exception as e:
        print(f"  [EntityTool] Place 검색 오류: {e}")
        return []
