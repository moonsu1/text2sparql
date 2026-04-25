"""
End-to-End Test Script
1단계: Synthetic Data 생성
2단계: RDF로 변환

간단히 두 단계를 연속 실행하는 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.append(str(Path(__file__).parent))

from app.step1_generate.generate_synthetic_data import SyntheticLogGenerator
from app.step2_transform.build_rdf_from_logs import LogToRDFConverter


def main():
    print("=" * 70)
    print("Smartphone Log to RDF Pipeline Test")
    print("=" * 70)
    
    # Step 1: Synthetic Data 생성
    print("\n[Step 1/2] Synthetic Data 생성...")
    generator = SyntheticLogGenerator(num_days=7)
    generator.generate_all()
    generator.save_to_files()
    
    # Step 2: RDF 변환
    print("\n[Step 2/2] RDF 변환...")
    converter = LogToRDFConverter()
    converter.convert_all()
    converter.save()
    
    print("\n" + "=" * 70)
    print("Pipeline 실행 완료!")
    print("=" * 70)
    print("\n다음 파일들을 확인하세요:")
    print("  data/synthetic_logs/*.json  - 생성된 로그 파일")
    print("  data/rdf/generated_data.ttl - 변환된 RDF 파일")


if __name__ == "__main__":
    main()
