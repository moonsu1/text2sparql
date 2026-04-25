"""
In-Memory SPARQL Executor
Fuseki 대신 rdflib의 내장 SPARQL 엔진 사용
Docker 없이도 SPARQL 쿼리 실행 가능
"""

import sys
from pathlib import Path
from rdflib import Graph
from typing import List, Dict, Any

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.config import RDF_OUTPUT_DIR


class InMemorySPARQLExecutor:
    """In-memory SPARQL executor using rdflib"""
    
    def __init__(self):
        self.graph = Graph()
        self.loaded = False
    
    def load_rdf_file(self, rdf_file_path: Path):
        """RDF 파일을 메모리에 로드"""
        if not rdf_file_path.exists():
            print(f"[ERROR] 파일이 없습니다: {rdf_file_path}")
            return False
        
        print(f"\n[LOAD] RDF 파일 로딩 중: {rdf_file_path.name}")
        
        try:
            self.graph.parse(rdf_file_path, format="turtle")
            triple_count = len(self.graph)
            print(f"[OK] {triple_count}개 triples 로드 완료")
            self.loaded = True
            return True
        except Exception as e:
            print(f"[ERROR] RDF 로딩 실패: {e}")
            return False
    
    def execute_query(self, sparql_query: str) -> List[Dict[str, Any]]:
        """SPARQL SELECT 쿼리 실행"""
        if not self.loaded:
            print("[ERROR] RDF 데이터가 로드되지 않았습니다")
            return []
        
        try:
            results = self.graph.query(sparql_query)
            
            # rdflib 결과를 딕셔너리 리스트로 변환
            result_list = []
            for row in results:
                row_dict = {}
                for var in results.vars:
                    value = row[var]
                    if value is not None:
                        row_dict[str(var)] = str(value)
                result_list.append(row_dict)
            
            return result_list
        except Exception as e:
            print(f"[ERROR] 쿼리 실행 실패: {e}")
            return []
    
    def count_triples(self) -> int:
        """Triple 개수 확인"""
        return len(self.graph)
    
    def get_graph(self) -> Graph:
        """내부 그래프 반환"""
        return self.graph


def main():
    """테스트 실행"""
    print("=" * 60)
    print("In-Memory SPARQL Executor Test")
    print("=" * 60)
    
    executor = InMemorySPARQLExecutor()
    
    # RDF 로드
    rdf_file = RDF_OUTPUT_DIR / "generated_data.ttl"
    if not executor.load_rdf_file(rdf_file):
        return
    
    print(f"\n[INFO] 총 {executor.count_triples()}개 triples")
    
    # 간단한 테스트 쿼리
    test_query = """
    PREFIX log: <http://example.org/smartphone-log#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?event ?label
    WHERE {
        ?event a log:CallEvent .
        ?event rdfs:label ?label .
    }
    LIMIT 5
    """
    
    print("\n[TEST] CallEvent 조회 테스트")
    results = executor.execute_query(test_query)
    
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result.get('label', 'N/A')}")
    
    print("\n[OK] SPARQL 엔진 동작 확인 완료!")


if __name__ == "__main__":
    main()
