"""
Explanation Layer
SPARQL 결과를 자연어로 설명
Provenance 정보와 함께 근거 제시
"""

from typing import List, Dict, Any
from datetime import datetime


class ExplanationGenerator:
    """SPARQL 결과 설명 생성기"""
    
    def __init__(self):
        pass
    
    def explain_recent_calls(self, results: List[Dict], analysis: Dict) -> str:
        """최근 통화 결과 설명"""
        if not results:
            return "최근 통화 기록이 없습니다."
        
        time_word = analysis.get("time_constraint", {}).get("word", "최근")
        
        explanation = f"{time_word} 통화한 사람들:\n"
        for i, row in enumerate(results, 1):
            person_name = row.get("personName", "알 수 없음")
            time_str = row.get("time", "")
            
            # ISO datetime을 한국어로 변환
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                time_display = dt.strftime("%m월 %d일 %H시 %M분")
            except:
                time_display = time_str
            
            explanation += f"  {i}. {person_name}님 ({time_display})\n"
        
        # 근거 이벤트 ID 추출
        event_ids = [row.get("call", "").split("/")[-1] for row in results if row.get("call")]
        if event_ids:
            explanation += f"\n근거: {', '.join(event_ids[:3])}"
            if len(event_ids) > 3:
                explanation += f" 외 {len(event_ids)-3}건"
        
        return explanation
    
    def explain_call_after_cafe(self, results: List[Dict], analysis: Dict) -> str:
        """통화 후 카페 방문 설명"""
        if not results:
            person = analysis.get("person_mention", "해당 사람")
            return f"{person}님과 통화 후 방문한 카페가 없습니다."
        
        row = results[0]
        person_name = row.get("personName", "알 수 없음")
        cafe_name = row.get("cafeName", "알 수 없음")
        
        call_time_str = row.get("callTime", "")
        visit_time_str = row.get("visitTime", "")
        
        try:
            call_dt = datetime.fromisoformat(call_time_str.replace("Z", "+00:00"))
            visit_dt = datetime.fromisoformat(visit_time_str.replace("Z", "+00:00"))
            
            call_display = call_dt.strftime("%H시 %M분")
            visit_display = visit_dt.strftime("%H시 %M분")
            
            time_diff = int((visit_dt - call_dt).total_seconds() / 60)
            
            explanation = f"{person_name}님과 통화({call_display}) 후 약 {time_diff}분 뒤에 "
            explanation += f"{cafe_name}에 방문하셨습니다 ({visit_display}).\n"
        except:
            explanation = f"{person_name}님과 통화 후 {cafe_name}에 방문하셨습니다.\n"
        
        # 근거
        call_id = row.get("call", "").split("/")[-1]
        visit_id = row.get("visit", "").split("/")[-1]
        explanation += f"\n근거: {call_id}, {visit_id}"
        
        return explanation
    
    def explain_most_used_app(self, results: List[Dict], analysis: Dict) -> str:
        """가장 많이 사용한 앱 설명"""
        if not results:
            return "앱 사용 기록이 없습니다."
        
        row = results[0]
        app_name = row.get("appName", "알 수 없음")
        count = row.get("count", "0")
        
        time_word = analysis.get("time_constraint", {}).get("word", "최근")
        
        explanation = f"{time_word} 가장 많이 사용한 앱은 {app_name}입니다 ({count}회)."
        
        return explanation
    
    def explain_meeting_location(self, results: List[Dict], analysis: Dict) -> str:
        """회의 장소 설명"""
        if not results:
            time_word = analysis.get("time_constraint", {}).get("word", "해당 시간")
            return f"{time_word}에 회의 일정이 없습니다."
        
        explanations = []
        for row in results:
            title = row.get("title", "일정")
            location = row.get("location", "장소 정보 없음")
            
            # location에서 "Location: " 제거
            if "Location:" in location:
                location = location.replace("Location:", "").strip()
            
            start_time_str = row.get("startTime", "")
            
            try:
                start_dt = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                time_display = start_dt.strftime("%m월 %d일 %H시")
            except:
                time_display = "시간 정보 없음"
            
            explanations.append(f"- {title} ({time_display}): {location}")
        
        result_text = "\n".join(explanations)
        return f"회의 일정:\n{result_text}"
    
    def explain_visited_places(self, results: List[Dict], analysis: Dict) -> str:
        """방문 장소 설명"""
        if not results:
            return "방문 기록이 없습니다."
        
        time_word = analysis.get("time_constraint", {}).get("word", "최근")
        
        explanation = f"{time_word} 방문한 장소:\n"
        for i, row in enumerate(results, 1):
            place_name = row.get("placeName", "알 수 없음")
            visit_time_str = row.get("visitTime", "")
            
            try:
                visit_dt = datetime.fromisoformat(visit_time_str.replace("Z", "+00:00"))
                time_display = visit_dt.strftime("%m월 %d일 %H시 %M분")
            except:
                time_display = visit_time_str
            
            explanation += f"  {i}. {place_name} ({time_display})\n"
        
        return explanation
    
    def explain_photos_at_place(self, results: List[Dict], analysis: Dict) -> str:
        """장소에서 찍은 사진 설명"""
        if not results:
            return "해당 장소에서 찍은 사진이 없습니다."
        
        place_names = set(row.get("placeName", "") for row in results)
        place_name = list(place_names)[0] if place_names else "해당 장소"
        
        explanation = f"{place_name}에서 찍은 사진 {len(results)}장이 있습니다:\n"
        
        for i, row in enumerate(results, 1):
            captured_time_str = row.get("capturedTime", "")
            
            try:
                captured_dt = datetime.fromisoformat(captured_time_str.replace("Z", "+00:00"))
                time_display = captured_dt.strftime("%m월 %d일 %H시 %M분")
            except:
                time_display = captured_time_str
            
            photo_id = row.get("photo", "").split("/")[-1]
            explanation += f"  {i}. {photo_id} ({time_display})\n"
        
        return explanation
    
    def generate(self, intent: str, results: List[Dict], analysis: Dict) -> str:
        """Intent에 따라 적절한 설명 생성"""
        
        if intent == "recent_calls":
            return self.explain_recent_calls(results, analysis)
        elif intent == "call_after_visit_cafe":
            return self.explain_call_after_cafe(results, analysis)
        elif intent == "most_used_app":
            return self.explain_most_used_app(results, analysis)
        elif intent == "meeting_location":
            return self.explain_meeting_location(results, analysis)
        elif intent == "visited_places":
            return self.explain_visited_places(results, analysis)
        elif intent == "photos_at_place":
            return self.explain_photos_at_place(results, analysis)
        else:
            # 기본 설명
            if not results:
                return "결과가 없습니다."
            return f"{len(results)}개의 결과를 찾았습니다."


def main():
    """테스트"""
    print("Explanation Generator Ready")


if __name__ == "__main__":
    main()
