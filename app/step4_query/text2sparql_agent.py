"""
Simple Text2SPARQL Agent
Rule-based approach로 자연어 질의를 SPARQL로 변환

Intent 기반 템플릿 선택 방식
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.step4_query.templates import INTENT_TEMPLATES


class Text2SPARQLAgent:
    """간단한 rule-based Text2SPARQL 변환기"""
    
    def __init__(self):
        # Intent 패턴 정의
        self.intent_patterns = {
            "recent_calls": [
                r"최근.*통화.*사람",
                r"통화.*누구",
                r"전화.*누구",
                r"최근.*전화",
            ],
            "call_after_visit_cafe": [
                r"통화.*(?:후|뒤|다음).*카페",
                r"전화.*(?:후|뒤|다음).*카페",
                r".*카페.*(?:갔|갔다|들렀)",
            ],
            "most_used_app": [
                r"가장.*자주.*(?:쓴|사용한).*앱",
                r"많이.*(?:쓴|사용한).*앱",
                r"제일.*많이.*앱",
            ],
            "meeting_location": [
                r"회의.*어디",
                r"미팅.*장소",
                r"일정.*어디",
            ],
            "visited_places": [
                r"방문.*장소",
                r"(?:갔던|간|다녀온).*(?:곳|장소)",
                r"어디.*(?:갔|다녀왔)",
            ],
            "photos_at_place": [
                r"사진.*(?:있|찍)",
                r"찍은.*사진",
                r"(?:장소|곳).*사진",
            ],
        }
        
        # 시간 표현 패턴
        self.time_patterns = {
            "어제": -1,
            "그제": -2,
            "오늘": 0,
            "최근": -7,
            "지난주": -7,
            "이번주": -7,
        }
        
        # 사람 이름 패턴 (config의 CONTACTS 활용)
        from app.config import CONTACTS
        self.known_persons = {name.replace(" ", "").replace("-", ""): name for name in CONTACTS}
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """자연어 질의 분석"""
        analysis = {
            "original_query": query,
            "intent": None,
            "time_constraint": None,
            "person_mention": None,
            "place_type": None,
            "limit": 5
        }
        
        # Intent 분류
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    analysis["intent"] = intent
                    break
            if analysis["intent"]:
                break
        
        # 시간 표현 추출
        for time_word, days_ago in self.time_patterns.items():
            if time_word in query:
                target_date = datetime.now() + timedelta(days=days_ago)
                analysis["time_constraint"] = {
                    "word": time_word,
                    "date": target_date.date(),
                    "start_datetime": target_date.replace(hour=0, minute=0, second=0).isoformat()
                }
                break
        
        # 사람 이름 추출
        for person_id, person_name in self.known_persons.items():
            if person_name in query or person_id in query:
                analysis["person_mention"] = person_name
                break
        
        # 장소 유형 추출
        place_types = ["카페", "식당", "회사", "집"]
        for ptype in place_types:
            if ptype in query:
                analysis["place_type"] = ptype
                break
        
        return analysis
    
    def generate_sparql(self, analysis: Dict[str, Any]) -> Optional[str]:
        """분석 결과를 바탕으로 SPARQL 생성"""
        intent = analysis["intent"]
        
        if not intent or intent not in INTENT_TEMPLATES:
            return None
        
        template = INTENT_TEMPLATES[intent]
        
        # 파라미터 준비
        params = {
            "limit": analysis.get("limit", 5)
        }
        
        # 시간 필터 생성
        if analysis.get("time_constraint"):
            start_time = analysis["time_constraint"]["start_datetime"]
            params["start_time"] = start_time
            params["time_filter"] = f'FILTER(?time > "{start_time}"^^xsd:dateTime)'
        else:
            # 기본값: 최근 7일
            default_start = (datetime.now() - timedelta(days=7)).replace(hour=0, minute=0).isoformat()
            params["start_time"] = default_start
            params["time_filter"] = f'FILTER(?time > "{default_start}"^^xsd:dateTime)'
        
        # 사람 필터 생성
        if analysis.get("person_mention"):
            person_id = analysis["person_mention"].replace(" ", "").replace("-", "")
            params["person_filter"] = f'FILTER(?person = data:{person_id})'
        else:
            params["person_filter"] = ""
        
        # 장소 타입 필터
        if analysis.get("place_type"):
            place_type_map = {
                "카페": "cafe",
                "식당": "restaurant",
                "회사": "office",
                "집": "home"
            }
            ptype = place_type_map.get(analysis["place_type"], "cafe")
            params["place_type_filter"] = f'FILTER(?placeType = "{ptype}")'
        else:
            params["place_type_filter"] = ""
        
        # 템플릿에 파라미터 적용
        try:
            sparql = template.format(**params)
            return sparql
        except KeyError as e:
            print(f"[ERROR] 템플릿 파라미터 오류: {e}")
            return None
    
    def convert(self, query: str) -> Dict[str, Any]:
        """Text → SPARQL 전체 변환 프로세스"""
        print(f"\n[QUERY] {query}")
        
        # 1. 질의 분석
        analysis = self.analyze_query(query)
        print(f"[INTENT] {analysis['intent']}")
        
        if analysis.get("time_constraint"):
            print(f"[TIME] {analysis['time_constraint']['word']} ({analysis['time_constraint']['date']})")
        
        if analysis.get("person_mention"):
            print(f"[PERSON] {analysis['person_mention']}")
        
        # 2. SPARQL 생성
        sparql = self.generate_sparql(analysis)
        
        if not sparql:
            print("[ERROR] SPARQL 생성 실패")
            return {
                "success": False,
                "analysis": analysis,
                "sparql": None
            }
        
        print("[SPARQL] 생성 완료")
        
        return {
            "success": True,
            "analysis": analysis,
            "sparql": sparql
        }


def main():
    """테스트 실행"""
    print("=" * 60)
    print("Text2SPARQL Agent Test")
    print("=" * 60)
    
    agent = Text2SPARQLAgent()
    
    # 테스트 질의
    test_queries = [
        "최근 통화한 사람은 누구야?",
        "김철수랑 통화하고 나서 들른 카페 어디였지?",
        "최근 가장 자주 쓴 앱 뭐야?",
        "어제 회의는 어디서 했어?",
    ]
    
    for query in test_queries:
        result = agent.convert(query)
        if result["success"]:
            print("\n" + "="*60)
            print(result["sparql"][:200] + "...")
        print()


if __name__ == "__main__":
    main()
