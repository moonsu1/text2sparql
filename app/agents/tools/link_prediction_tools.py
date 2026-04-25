"""
Link Prediction Tools
GCN+TransE 기반 missing link 예측 도구
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from app.config import FUSEKI_URL, FUSEKI_DATASET, RDF_OUTPUT_DIR


_link_prediction_pipeline = None


def _get_pipeline():
    """Link prediction pipeline 싱글톤"""
    global _link_prediction_pipeline
    if _link_prediction_pipeline is None:
        from app.step3_load.fuseki_executor import FusekiSPARQLExecutor
        from app.link_prediction.pipeline import LinkPredictionPipeline
        
        executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
        _link_prediction_pipeline = LinkPredictionPipeline(
            rdf_graph=executor.graph,
            hidden_dim=64,
            num_gcn_layers=2
        )
        print("[LinkTool] Link Prediction 빠른 학습 (5 epochs)...")
        _link_prediction_pipeline.train(num_epochs=5, verbose=False)
    return _link_prediction_pipeline


def check_sparse_data(person_name: str) -> Dict[str, Any]:
    """
    특정 Person의 관련 데이터가 sparse한지 확인
    
    Args:
        person_name: 검색할 사람 이름 (영어)
    
    Returns:
        {"is_sparse": bool, "relation_count": int}
    """
    try:
        from app.step3_load.fuseki_executor import FusekiSPARQLExecutor
        executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
        
        query = f"""
        PREFIX log: <http://example.org/smartphone-log#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(?event) AS ?count) WHERE {{
            ?person rdfs:label ?label .
            FILTER(CONTAINS(?label, "{person_name}"))
            ?event ?p ?person .
        }}
        """
        
        results = executor.execute_query(query)
        count = int(results[0].get("count", "0")) if results else 0
        
        is_sparse = count < 3
        print(f"  [LinkTool] '{person_name}' 관련 triple: {count}개, sparse: {is_sparse}")
        
        return {"is_sparse": is_sparse, "relation_count": count}
    except Exception as e:
        print(f"  [LinkTool] Sparse 확인 오류: {e}")
        return {"is_sparse": False, "relation_count": 0}


def predict_missing_links_for_person(
    person_name: str,
    relation_type: str = "http://example.org/smartphone-log#visitedAfter"
) -> List[Tuple[str, str, float]]:
    """
    Person과 관련된 missing link 예측 (GCN+TransE)
    
    Args:
        person_name: 사람 이름 (영어)
        relation_type: 예측할 관계 타입 URI
    
    Returns:
        [(head_uri, tail_uri, confidence), ...] 예측된 triple 목록
    """
    try:
        from app.step3_load.fuseki_executor import FusekiSPARQLExecutor
        executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
        
        # 해당 Person의 CallEvent 찾기
        query = f"""
        PREFIX log: <http://example.org/smartphone-log#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?call WHERE {{
            ?call a log:CallEvent .
            ?call log:calledPerson ?person .
            ?person rdfs:label ?label .
            FILTER(CONTAINS(?label, "{person_name}"))
        }}
        LIMIT 1
        """
        
        results = executor.execute_query(query)
        if not results:
            print(f"  [LinkTool] '{person_name}' CallEvent 없음")
            return []
        
        call_uri = results[0].get("call", "")
        pipeline = _get_pipeline()
        
        predictions = pipeline.predict_missing_links(
            head_uri=call_uri,
            relation_uri=relation_type,
            top_k=3
        )
        
        result = [(call_uri, tail_uri, conf) for tail_uri, conf in predictions]
        print(f"  [LinkTool] {len(result)}개 triple 예측 완료")
        return result
    
    except Exception as e:
        print(f"  [LinkTool] 예측 오류: {e}")
        return []
