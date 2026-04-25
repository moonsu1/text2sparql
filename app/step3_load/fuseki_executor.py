"""
Fuseki SPARQL Executor
Apache Jena Fuseki를 사용한 SPARQL 쿼리 실행
InMemorySPARQLExecutor와 동일한 인터페이스 제공
"""

import sys
import requests
from pathlib import Path
from typing import List, Dict, Any

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.step3_load.load_to_fuseki import FusekiLoader
from app.config import FUSEKI_URL, FUSEKI_DATASET, RDF_OUTPUT_DIR


class FusekiSPARQLExecutor:
    """Fuseki SPARQL executor with automatic data loading"""
    
    def __init__(self, fuseki_url: str = None, dataset: str = None,
                 auth_user: str = "admin", auth_password: str = "admin123"):
        self.fuseki_url = (fuseki_url or FUSEKI_URL).rstrip('/')
        self.dataset = dataset or FUSEKI_DATASET
        self.query_url = f"{self.fuseki_url}/{self.dataset}/query"
        self.update_url = f"{self.fuseki_url}/{self.dataset}/update"
        self.loader = FusekiLoader(self.fuseki_url, self.dataset, auth_user, auth_password)
        self.auth = (auth_user, auth_password) if auth_user else None
        self.loaded = False
    
    def check_connection(self) -> bool:
        """Fuseki 서버 연결 확인"""
        try:
            response = requests.get(f"{self.fuseki_url}/$/ping", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def count_triples(self) -> int:
        """저장된 triple 개수 확인"""
        sparql_count = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
        
        try:
            response = requests.post(
                self.query_url,
                data={"query": sparql_count},
                headers={"Accept": "application/sparql-results+json"},
                auth=self.auth,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                count = int(result["results"]["bindings"][0]["count"]["value"])
                return count
            else:
                return -1
        except Exception as e:
            print(f"[ERROR] Triple 카운트 중 오류: {e}")
            return -1
    
    def ensure_data_loaded(self, rdf_file: Path):
        """데이터가 없으면 자동 적재"""
        if not self.check_connection():
            raise ConnectionError(f"Fuseki 서버에 연결할 수 없습니다: {self.fuseki_url}")
        
        triple_count = self.count_triples()
        
        if triple_count == 0:
            print(f"[AUTO-LOAD] Fuseki에 데이터가 없습니다. 자동 적재 시작...")
            success = self.loader.upload_rdf_file(rdf_file)
            if success:
                self.loaded = True
                final_count = self.count_triples()
                print(f"[OK] {final_count}개 triples 로드 완료")
            else:
                raise Exception("Fuseki 데이터 적재 실패")
        else:
            print(f"[OK] Fuseki에 이미 {triple_count}개 triples가 적재되어 있습니다")
            self.loaded = True
    
    def load_rdf_file(self, rdf_file_path: Path):
        """RDF 파일을 Fuseki에 로드 (InMemorySPARQLExecutor 호환)"""
        if not rdf_file_path.exists():
            print(f"[ERROR] 파일이 없습니다: {rdf_file_path}")
            return False
        
        self.ensure_data_loaded(rdf_file_path)
        return True
    
    def execute_query(self, sparql_query: str) -> List[Dict[str, Any]]:
        """SPARQL SELECT 쿼리 실행 (Fuseki)"""
        if not self.check_connection():
            print("[ERROR] Fuseki 서버에 연결할 수 없습니다")
            return []
        
        try:
            response = requests.post(
                self.query_url,
                data={"query": sparql_query},
                headers={"Accept": "application/sparql-results+json"},
                auth=self.auth,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"[ERROR] Fuseki 쿼리 실패: {response.status_code}")
                print(f"응답: {response.text[:500]}")
                return []
            
            # Fuseki JSON 결과를 List[Dict]로 변환
            result_json = response.json()
            return self._parse_results(result_json)
        
        except Exception as e:
            print(f"[ERROR] 쿼리 실행 실패: {e}")
            return []
    
    def _parse_results(self, fuseki_json: dict) -> List[Dict[str, Any]]:
        """Fuseki JSON을 표준 Dict 리스트로 변환"""
        results = []
        
        if "results" not in fuseki_json or "bindings" not in fuseki_json["results"]:
            return results
        
        for binding in fuseki_json["results"]["bindings"]:
            row = {}
            for var, value_obj in binding.items():
                # value만 추출 (type, datatype 등은 제외)
                row[var] = value_obj["value"]
            results.append(row)
        
        return results
    
    def get_graph(self):
        """내부 그래프 반환 (InMemorySPARQLExecutor 호환, Fuseki에서는 None)"""
        print("[WARNING] Fuseki는 get_graph()를 지원하지 않습니다")
        return None


def main():
    """테스트 실행"""
    print("=" * 60)
    print("Fuseki SPARQL Executor Test")
    print("=" * 60)
    
    executor = FusekiSPARQLExecutor()
    
    # 연결 확인
    if not executor.check_connection():
        print("[ERROR] Fuseki 서버에 연결할 수 없습니다")
        print(f"Fuseki URL: {executor.fuseki_url}")
        print("\nFuseki를 시작하세요: docker-compose up -d fuseki")
        return
    
    print(f"[OK] Fuseki 서버 연결 성공: {executor.fuseki_url}")
    
    # 데이터 로드
    rdf_file = RDF_OUTPUT_DIR / "generated_data.ttl"
    executor.ensure_data_loaded(rdf_file)
    
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
