"""
Fuseki 수동 데이터 적재 스크립트
RDF 데이터를 Fuseki에 수동으로 적재하거나 재적재
"""

import sys
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.step3_load.load_to_fuseki import FusekiLoader
from app.config import FUSEKI_URL, FUSEKI_DATASET, RDF_OUTPUT_DIR


def main():
    parser = argparse.ArgumentParser(description="Fuseki 데이터 적재 스크립트")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="기존 데이터 삭제 후 적재"
    )
    parser.add_argument(
        "--file",
        type=str,
        default="generated_data.ttl",
        help="RDF 파일명 (기본: generated_data.ttl)"
    )
    parser.add_argument(
        "--fuseki-url",
        type=str,
        default=FUSEKI_URL,
        help=f"Fuseki URL (기본: {FUSEKI_URL})"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=FUSEKI_DATASET,
        help=f"Dataset 이름 (기본: {FUSEKI_DATASET})"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Fuseki 수동 데이터 적재")
    print("=" * 70)
    
    # Fuseki Loader 초기화
    loader = FusekiLoader(args.fuseki_url, args.dataset)
    
    # 1. 연결 확인
    print(f"\n[1/4] Fuseki 서버 연결 확인 중...")
    if not loader.check_connection():
        print("\n[ERROR] Fuseki 서버에 연결할 수 없습니다")
        print(f"URL: {args.fuseki_url}")
        print("\nFuseki를 시작하세요:")
        print("  docker-compose up -d fuseki")
        return 1
    
    print(f"[OK] Fuseki 연결 성공: {args.fuseki_url}")
    
    # 2. 기존 데이터 확인
    print(f"\n[2/4] 기존 데이터 확인 중...")
    existing_count = loader.count_triples()
    
    if existing_count > 0:
        print(f"[INFO] 기존 데이터: {existing_count}개 triples")
        
        if args.clear:
            print("[CLEAR] 기존 데이터 삭제 중...")
            loader.clear_dataset()
        else:
            print("[INFO] 기존 데이터 유지 (--clear 옵션으로 삭제 가능)")
    else:
        print("[INFO] 기존 데이터 없음")
    
    # 3. RDF 파일 업로드
    print(f"\n[3/4] RDF 파일 업로드 중...")
    rdf_file = RDF_OUTPUT_DIR / args.file
    
    if not rdf_file.exists():
        print(f"[ERROR] 파일이 없습니다: {rdf_file}")
        print("\n데이터를 먼저 생성하세요:")
        print("  python test_pipeline.py")
        return 1
    
    success = loader.upload_rdf_file(rdf_file)
    
    if not success:
        print("\n[FAIL] RDF 업로드 실패")
        return 1
    
    # 4. 적재 확인
    print(f"\n[4/4] 적재 결과 확인 중...")
    final_count = loader.count_triples()
    print(f"[OK] 총 {final_count}개 triples 적재 완료")
    
    print("\n" + "=" * 70)
    print("Fuseki 데이터 적재 완료!")
    print("=" * 70)
    print(f"\nFuseki UI: {args.fuseki_url}")
    print(f"Query endpoint: {loader.query_url}")
    print(f"\n웹 UI에서 확인하세요: {args.fuseki_url}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
