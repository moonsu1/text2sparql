"""
End-to-End Integration Test
전체 파이프라인 통합 테스트:
1. 자연어 질의
2. SPARQL 생성
3. 쿼리 실행
4. 결과 설명
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from app.step3_load.fuseki_executor import FusekiSPARQLExecutor
from app.step4_query.text2sparql_agent import Text2SPARQLAgent
from app.step5_explain.explanation import ExplanationGenerator
from app.config import RDF_OUTPUT_DIR, FUSEKI_URL, FUSEKI_DATASET


class SmartphoneLogQASystem:
    """스마트폰 로그 QA 시스템"""
    
    def __init__(self):
        # 1. SPARQL Executor 초기화 (Fuseki)
        self.executor = FusekiSPARQLExecutor(FUSEKI_URL, FUSEKI_DATASET)
        
        # 2. Text2SPARQL Agent 초기화
        self.agent = Text2SPARQLAgent()
        
        # 3. Explanation Generator 초기화
        self.explainer = ExplanationGenerator()
        
        self.loaded = False
    
    def load_data(self, rdf_file_path: Path = None):
        """RDF 데이터 로드"""
        if rdf_file_path is None:
            rdf_file_path = RDF_OUTPUT_DIR / "generated_data.ttl"
        
        print("\n[INIT] RDF 데이터 로딩...")
        success = self.executor.load_rdf_file(rdf_file_path)
        
        if success:
            self.loaded = True
            print(f"[OK] 시스템 준비 완료! ({self.executor.count_triples()} triples)")
        else:
            print("[FAIL] 데이터 로딩 실패")
        
        return success
    
    def ask(self, natural_language_query: str) -> str:
        """자연어 질의 → SPARQL → 실행 → 설명"""
        
        if not self.loaded:
            return "[ERROR] 데이터가 로드되지 않았습니다. load_data()를 먼저 호출하세요."
        
        print("\n" + "=" * 70)
        print(f"질문: {natural_language_query}")
        print("=" * 70)
        
        # Step 1: Text → SPARQL
        conversion_result = self.agent.convert(natural_language_query)
        
        if not conversion_result["success"]:
            return "[ERROR] SPARQL 생성 실패. 다른 방식으로 질문해주세요."
        
        analysis = conversion_result["analysis"]
        sparql_query = conversion_result["sparql"]
        
        print(f"\n[SPARQL]\n{sparql_query[:300]}...")
        
        # Step 2: SPARQL 실행
        print("\n[EXECUTE] 쿼리 실행 중...")
        results = self.executor.execute_query(sparql_query)
        print(f"[RESULT] {len(results)}개 결과")
        
        # Step 3: 결과 설명
        explanation = self.explainer.generate(
            analysis["intent"],
            results,
            analysis
        )
        
        return explanation


def main():
    """시나리오 테스트"""
    print("=" * 70)
    print("Smartphone Log QA System - End-to-End Test")
    print("=" * 70)
    
    # 시스템 초기화
    qa_system = SmartphoneLogQASystem()
    
    if not qa_system.load_data():
        print("\n[FAIL] 시스템 초기화 실패")
        return
    
    print("\n\n" + "=" * 70)
    print("시나리오 테스트 시작")
    print("=" * 70)
    
    # 테스트 시나리오
    test_scenarios = [
        {
            "query": "최근 통화한 사람은 누구야?",
            "description": "최근 통화 기록 조회"
        },
        {
            "query": "최근 가장 자주 쓴 앱 뭐야?",
            "description": "가장 많이 사용한 앱 조회"
        },
        {
            "query": "어제 방문한 장소 어디야?",
            "description": "어제 방문한 장소 조회"
        },
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n\n{'='*70}")
        print(f"시나리오 #{i}: {scenario['description']}")
        print(f"{'='*70}")
        
        answer = qa_system.ask(scenario["query"])
        
        print(f"\n[답변]\n{answer}")
        print("\n" + "-"*70)
    
    print("\n\n" + "=" * 70)
    print("End-to-End 테스트 완료!")
    print("=" * 70)
    
    # 통계
    print(f"\nTriple Store 통계:")
    print(f"  - 총 Triples: {qa_system.executor.count_triples()}개")
    print(f"  - 지원 Intent: {len(qa_system.agent.intent_patterns)}개")


if __name__ == "__main__":
    main()
