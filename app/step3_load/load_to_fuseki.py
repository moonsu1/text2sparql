"""
Load RDF Data to Apache Jena Fuseki
RDF 데이터를 Fuseki triple store에 적재
"""

import requests
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.config import (
    FUSEKI_URL,
    FUSEKI_DATASET,
    RDF_OUTPUT_DIR
)


class FusekiLoader:
    """Fuseki에 RDF 데이터를 적재하는 클래스"""
    
    def __init__(self, fuseki_url: str = FUSEKI_URL, dataset: str = FUSEKI_DATASET, 
                 auth_user: str = "admin", auth_password: str = "admin123"):
        self.fuseki_url = fuseki_url.rstrip('/')
        self.dataset = dataset
        self.upload_url = f"{self.fuseki_url}/{self.dataset}/data"
        self.query_url = f"{self.fuseki_url}/{self.dataset}/query"
        self.update_url = f"{self.fuseki_url}/{self.dataset}/update"
        self.auth = (auth_user, auth_password) if auth_user else None
    
    def check_connection(self) -> bool:
        """Fuseki 서버 연결 확인"""
        try:
            response = requests.get(f"{self.fuseki_url}/$/ping", timeout=5)
            if response.status_code == 200:
                print(f"[OK] Fuseki 서버 연결 성공: {self.fuseki_url}")
                return True
            else:
                print(f"[ERROR] Fuseki 서버 응답 오류: {response.status_code}")
                return False
        except requests.ConnectionError:
            print(f"[ERROR] Fuseki 서버에 연결할 수 없습니다: {self.fuseki_url}")
            print("Docker로 Fuseki를 실행하세요: docker-compose up -d")
            return False
        except Exception as e:
            print(f"[ERROR] 연결 확인 중 오류: {e}")
            return False
    
    def clear_dataset(self):
        """Dataset의 모든 데이터 삭제 (초기화)"""
        print(f"\n[CLEAR] Dataset '{self.dataset}' 초기화 중...")
        
        sparql_delete = "DELETE WHERE { ?s ?p ?o }"
        
        try:
            response = requests.post(
                self.update_url,
                data=sparql_delete,
                headers={"Content-Type": "application/sparql-update"},
                auth=self.auth,
                timeout=30
            )
            
            if response.status_code in [200, 204]:
                print("[OK] Dataset 초기화 완료")
            else:
                print(f"[WARNING] 초기화 실패: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[ERROR] 초기화 중 오류: {e}")
    
    def upload_rdf_file(self, rdf_file_path: Path):
        """RDF 파일을 Fuseki에 업로드"""
        if not rdf_file_path.exists():
            print(f"[ERROR] 파일이 없습니다: {rdf_file_path}")
            return False
        
        print(f"\n[UPLOAD] RDF 파일 업로드 중: {rdf_file_path.name}")
        
        with open(rdf_file_path, "rb") as f:
            rdf_data = f.read()
        
        try:
            response = requests.post(
                self.upload_url,
                data=rdf_data,
                headers={"Content-Type": "text/turtle; charset=utf-8"},
                auth=self.auth,
                timeout=60
            )
            
            if response.status_code in [200, 201, 204]:
                print(f"[OK] 업로드 성공!")
                return True
            else:
                print(f"[ERROR] 업로드 실패: {response.status_code}")
                print(f"응답: {response.text[:500]}")
                return False
        except Exception as e:
            print(f"[ERROR] 업로드 중 오류: {e}")
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
                print(f"\n[INFO] 현재 저장된 triples: {count}개")
                return count
            else:
                print(f"[ERROR] Triple 카운트 실패: {response.status_code}")
                return -1
        except Exception as e:
            print(f"[ERROR] Triple 카운트 중 오류: {e}")
            return -1
    
    def execute_query(self, sparql_query: str) -> dict:
        """SPARQL 쿼리 실행"""
        try:
            response = requests.post(
                self.query_url,
                data={"query": sparql_query},
                headers={"Accept": "application/sparql-results+json"},
                auth=self.auth,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ERROR] 쿼리 실행 실패: {response.status_code}")
                return None
        except Exception as e:
            print(f"[ERROR] 쿼리 실행 중 오류: {e}")
            return None


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("Fuseki RDF Data Loader")
    print("=" * 60)
    
    loader = FusekiLoader()
    
    # 1. 연결 확인
    if not loader.check_connection():
        return
    
    # 2. Dataset 초기화 (선택적)
    loader.clear_dataset()
    
    # 3. RDF 파일 업로드
    rdf_file = RDF_OUTPUT_DIR / "generated_data.ttl"
    success = loader.upload_rdf_file(rdf_file)
    
    if not success:
        print("\n[FAIL] RDF 업로드 실패")
        return
    
    # 4. Triple 개수 확인
    loader.count_triples()
    
    print("\n" + "=" * 60)
    print("Fuseki 적재 완료!")
    print("=" * 60)
    print(f"\nFuseki UI: {loader.fuseki_url}")
    print(f"Query endpoint: {loader.query_url}")


if __name__ == "__main__":
    main()
