"""
Execution Tools
SPARQL 실행 및 결과 검증 도구
"""

import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from app.config import FUSEKI_URL, FUSEKI_DATASET


def execute_sparql_on_fuseki(sparql: str) -> Dict[str, Any]:
    """
    Fuseki에 SPARQL 쿼리 실행
    
    Args:
        sparql: 실행할 SPARQL 쿼리
    
    Returns:
        {
            "results": List[dict],
            "count": int,
            "execution_time_ms": float,
            "error": str or None
        }
    """
    try:
        from app.step3_load.fuseki_executor import FusekiSPARQLExecutor
        executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
        
        start_time = time.time()
        results = executor.execute_query(sparql)
        execution_time = (time.time() - start_time) * 1000
        
        print(f"  [ExecTool] 실행 완료: {len(results)}건, {execution_time:.2f}ms")
        
        return {
            "results": results,
            "count": len(results),
            "execution_time_ms": execution_time,
            "error": None
        }
    except Exception as e:
        print(f"  [ExecTool] 실행 오류: {e}")
        return {
            "results": [],
            "count": 0,
            "execution_time_ms": 0.0,
            "error": str(e)
        }


def verify_results_quality(
    results: List[Dict[str, Any]],
    sparse_threshold: int = 3
) -> Dict[str, Any]:
    """
    SPARQL 실행 결과의 품질 검증
    
    Args:
        results: 실행 결과 목록
        sparse_threshold: sparse 판단 기준 개수
    
    Returns:
        {
            "is_complete": bool,
            "issue": str,   # "ok", "empty", "sparse"
            "suggestion": str
        }
    """
    count = len(results)
    
    if count == 0:
        return {
            "is_complete": False,
            "issue": "empty",
            "suggestion": "결과가 없습니다. 링크 예측으로 데이터를 보강하거나 SPARQL을 수정하세요."
        }
    
    if count < sparse_threshold:
        return {
            "is_complete": False,
            "issue": "sparse",
            "suggestion": f"결과가 {count}건으로 부족합니다. 링크 예측으로 보강할 수 있습니다."
        }
    
    return {
        "is_complete": True,
        "issue": "ok",
        "suggestion": None
    }
