"""
Synthetic Smartphone Log Data Generator
시나리오 기반 스마트폰 로그 생성기

핵심 전략:
- 단순 랜덤이 아니라 realistic한 하루 일과 패턴 생성
- 이벤트 간 시간적 연관성 부여
- 통화 후 카페 방문, 회의 중 사진 촬영 등의 연결 생성
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import sys

# 상위 디렉토리의 config import를 위한 경로 설정
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.config import (
    SYNTHETIC_LOGS_DIR,
    NUM_DAYS,
    USER_ID,
    CONTACTS,
    PLACES,
    APPS,
    ensure_directories
)


class SyntheticLogGenerator:
    """Synthetic 로그 생성기"""
    
    def __init__(self, num_days: int = NUM_DAYS, user_id: str = USER_ID):
        self.num_days = num_days
        self.user_id = user_id
        self.end_date = datetime.now().replace(hour=23, minute=59, second=0, microsecond=0)
        self.start_date = self.end_date - timedelta(days=num_days - 1)
        self.start_date = self.start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 생성된 데이터 저장
        self.call_logs = []
        self.app_usage_events = []
        self.calendar_events = []
        self.visit_events = []
        self.content_metadata = []
        
        # ID 카운터
        self.call_id_counter = 1
        self.app_event_id_counter = 1
        self.calendar_id_counter = 1
        self.visit_id_counter = 1
        self.content_id_counter = 1
    
    def generate_all(self):
        """모든 종류의 로그 생성"""
        print(f"[{self.start_date.date()} ~ {self.end_date.date()}] {self.num_days}일치 로그 생성 시작...")
        
        current_date = self.start_date
        
        for day_idx in range(self.num_days):
            print(f"\n  Day {day_idx + 1}: {current_date.date()}")
            
            # 평일인지 주말인지 판단
            is_weekend = current_date.weekday() >= 5
            
            # 하루 일과 생성 (시간 순서대로 연결된 이벤트)
            self._generate_daily_scenario(current_date, is_weekend)
            
            current_date += timedelta(days=1)
        
        print(f"\n생성 완료:")
        print(f"   - 통화 로그: {len(self.call_logs)}건")
        print(f"   - 앱 사용: {len(self.app_usage_events)}건")
        print(f"   - 캘린더 일정: {len(self.calendar_events)}건")
        print(f"   - 방문 이벤트: {len(self.visit_events)}건")
        print(f"   - 콘텐츠: {len(self.content_metadata)}건")
    
    def _generate_daily_scenario(self, date: datetime, is_weekend: bool):
        """하루 일과 시나리오 생성 (시간 순서대로 연결)"""
        
        if is_weekend:
            self._generate_weekend_scenario(date)
        else:
            self._generate_weekday_scenario(date)
    
    def _generate_weekday_scenario(self, date: datetime):
        """평일 시나리오"""
        timeline = []
        
        # 08:00 - 집 출발
        home_departure = date.replace(hour=8, minute=0) + timedelta(minutes=random.randint(-10, 10))
        timeline.append(("visit_departure", home_departure, "home"))
        
        # 08:15 - 출근길 앱 사용 (지하철)
        commute_time = home_departure + timedelta(minutes=15)
        timeline.append(("app_commute", commute_time, None))
        
        # 08:50 - 회사 도착
        office_arrival = commute_time + timedelta(minutes=35)
        timeline.append(("visit_arrival", office_arrival, "office"))
        
        # 09:00 - 업무 시작 (Slack 체크)
        work_start = office_arrival + timedelta(minutes=10)
        timeline.append(("app_work", work_start, None))
        
        # 10:00 - 오전 회의 (랜덤)
        if random.random() > 0.5:
            meeting_start = date.replace(hour=10, minute=0)
            timeline.append(("calendar_meeting", meeting_start, None))
        
        # 11:00 - 통화 (랜덤)
        if random.random() > 0.3:
            call_time = date.replace(hour=11, minute=5) + timedelta(minutes=random.randint(-30, 30))
            timeline.append(("call", call_time, None))
        
        # 12:00 - 점심 (카페 또는 식당)
        lunch_place = random.choice([p for p in PLACES if p["type"] in ["cafe", "restaurant"]])
        lunch_time = date.replace(hour=12, minute=0) + timedelta(minutes=random.randint(-15, 15))
        timeline.append(("visit_lunch", lunch_time, lunch_place["id"]))
        timeline.append(("photo_food", lunch_time + timedelta(minutes=5), lunch_place["id"]))
        
        # 14:00 - 오후 회의 (랜덤)
        if random.random() > 0.4:
            afternoon_meeting = date.replace(hour=14, minute=0)
            timeline.append(("calendar_meeting", afternoon_meeting, None))
        
        # 15:00 - 커피 브레이크
        if random.random() > 0.5:
            cafe = random.choice([p for p in PLACES if p["type"] == "cafe"])
            coffee_time = date.replace(hour=15, minute=30) + timedelta(minutes=random.randint(-20, 20))
            timeline.append(("visit_cafe", coffee_time, cafe["id"]))
        
        # 18:00 - 퇴근
        leave_office = date.replace(hour=18, minute=0) + timedelta(minutes=random.randint(-30, 60))
        timeline.append(("visit_departure", leave_office, "office"))
        
        # 18:30 - 퇴근길 앱 사용
        after_work = leave_office + timedelta(minutes=15)
        timeline.append(("app_commute", after_work, None))
        
        # 19:00 - 집 도착
        home_arrival = after_work + timedelta(minutes=30)
        timeline.append(("visit_arrival", home_arrival, "home"))
        
        # 타임라인을 실제 이벤트로 변환
        self._execute_timeline(timeline)
    
    def _generate_weekend_scenario(self, date: datetime):
        """주말 시나리오"""
        timeline = []
        
        # 10:00 - 늦은 기상, 집에서 앱 사용
        wake_up = date.replace(hour=10, minute=0) + timedelta(minutes=random.randint(-30, 60))
        timeline.append(("app_leisure", wake_up, None))
        
        # 12:00 - 브런치
        brunch_place = random.choice([p for p in PLACES if p["type"] in ["cafe", "restaurant"]])
        brunch_time = date.replace(hour=12, minute=0) + timedelta(minutes=random.randint(-30, 30))
        timeline.append(("visit_lunch", brunch_time, brunch_place["id"]))
        timeline.append(("photo_food", brunch_time + timedelta(minutes=10), brunch_place["id"]))
        
        # 14:00 - 쇼핑몰 또는 카페
        if random.random() > 0.5:
            afternoon_place = random.choice([p for p in PLACES if p["type"] in ["cafe", "shopping"]])
            afternoon_time = date.replace(hour=14, minute=30) + timedelta(minutes=random.randint(-30, 30))
            timeline.append(("visit_leisure", afternoon_time, afternoon_place["id"]))
        
        # 저녁 통화
        if random.random() > 0.3:
            evening_call = date.replace(hour=19, minute=0) + timedelta(minutes=random.randint(-60, 60))
            timeline.append(("call", evening_call, None))
        
        # 저녁 앱 사용 (OTT, 게임)
        evening_app = date.replace(hour=21, minute=0) + timedelta(minutes=random.randint(-60, 60))
        timeline.append(("app_entertainment", evening_app, None))
        
        self._execute_timeline(timeline)
    
    def _execute_timeline(self, timeline: List[tuple]):
        """타임라인을 실제 이벤트로 변환"""
        
        for event_type, event_time, context in timeline:
            if event_type == "call":
                self._create_call_event(event_time)
            
            elif event_type.startswith("app_"):
                category = event_type.split("_")[1]
                self._create_app_usage_event(event_time, category)
            
            elif event_type.startswith("calendar_"):
                self._create_calendar_event(event_time)
            
            elif event_type.startswith("visit_"):
                action = event_type.split("_")[1]
                if action in ["arrival", "lunch", "cafe", "leisure"]:
                    place_id = context
                    place = next(p for p in PLACES if p["id"] == place_id)
                    self._create_visit_event(event_time, place)
            
            elif event_type.startswith("photo_"):
                place_id = context
                place = next(p for p in PLACES if p["id"] == place_id)
                self._create_photo(event_time, place)
    
    def _create_call_event(self, time: datetime):
        """통화 이벤트 생성"""
        call_id = f"call_{self.call_id_counter:03d}"
        self.call_id_counter += 1
        
        callee = random.choice(CONTACTS)
        duration = random.randint(30, 600)  # 30초 ~ 10분
        call_type = random.choices(
            ["outgoing", "incoming", "missed"],
            weights=[0.5, 0.4, 0.1]
        )[0]
        
        self.call_logs.append({
            "call_id": call_id,
            "caller": self.user_id,
            "callee": callee,
            "started_at": time.isoformat(),
            "duration_seconds": duration,
            "call_type": call_type
        })
    
    def _create_app_usage_event(self, time: datetime, category: str):
        """앱 사용 이벤트 생성"""
        
        # 카테고리에 맞는 앱 선택
        category_map = {
            "commute": ["news", "social", "entertainment"],
            "work": ["work"],
            "leisure": ["social", "entertainment"],
            "entertainment": ["entertainment"]
        }
        
        allowed_categories = category_map.get(category, ["work", "social"])
        suitable_apps = [a for a in APPS if a["category"] in allowed_categories]
        
        if not suitable_apps:
            suitable_apps = APPS
        
        app = random.choice(suitable_apps)
        
        app_event_id = f"app_evt_{self.app_event_id_counter:03d}"
        self.app_event_id_counter += 1
        
        self.app_usage_events.append({
            "app_event_id": app_event_id,
            "user": self.user_id,
            "package_name": app["package"],
            "app_name": app["name"],
            "event_type": "opened",
            "occurred_at": time.isoformat(),
            "session_duration_seconds": random.randint(60, 1800)
        })
    
    def _create_calendar_event(self, start_time: datetime):
        """캘린더 이벤트 생성"""
        cal_id = f"cal_{self.calendar_id_counter:03d}"
        self.calendar_id_counter += 1
        
        meeting_titles = [
            "제품 기획 회의",
            "주간 스프린트 미팅",
            "1:1 미팅",
            "전체 회의",
            "디자인 리뷰",
            "코드 리뷰"
        ]
        
        title = random.choice(meeting_titles)
        duration = random.choice([30, 60, 90])  # 30분, 1시간, 1.5시간
        end_time = start_time + timedelta(minutes=duration)
        
        participants = random.sample(CONTACTS, k=random.randint(1, 3))
        
        self.calendar_events.append({
            "calendar_event_id": cal_id,
            "user": self.user_id,
            "title": title,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "location": "회의실 B",
            "participants": participants,
            "category": "work"
        })
    
    def _create_visit_event(self, time: datetime, place: Dict[str, Any]):
        """방문 이벤트 생성"""
        visit_id = f"visit_{self.visit_id_counter:03d}"
        self.visit_id_counter += 1
        
        stay_duration = random.randint(600, 3600)  # 10분 ~ 1시간
        
        self.visit_events.append({
            "visit_event_id": visit_id,
            "user": self.user_id,
            "place_name": place["name"],
            "place_type": place["type"],
            "visited_at": time.isoformat(),
            "wifi_ssid": place.get("wifi"),
            "lat": place["lat"],
            "lng": place["lng"],
            "stay_duration_seconds": stay_duration
        })
    
    def _create_photo(self, time: datetime, place: Dict[str, Any]):
        """사진 콘텐츠 생성"""
        content_id = f"photo_{self.content_id_counter:03d}"
        self.content_id_counter += 1
        
        tags = []
        if place["type"] == "cafe":
            tags = ["coffee", "food"]
        elif place["type"] == "restaurant":
            tags = ["food", "lunch"]
        
        self.content_metadata.append({
            "content_id": content_id,
            "user": self.user_id,
            "content_type": "photo",
            "captured_at": time.isoformat(),
            "place_name": place["name"],
            "lat": place["lat"],
            "lng": place["lng"],
            "linked_event_id": None,  # RDF 변환 시 VisitEvent와 연결
            "file_path": f"/storage/photos/{time.strftime('%Y-%m-%d_%H-%M-%S')}.jpg",
            "tags": tags
        })
    
    def save_to_files(self):
        """생성된 데이터를 JSON 파일로 저장"""
        ensure_directories()
        
        files = [
            ("call_logs.json", self.call_logs),
            ("app_usage.json", self.app_usage_events),
            ("calendar_instances.json", self.calendar_events),
            ("visit_events.json", self.visit_events),
            ("content_metadata.json", self.content_metadata)
        ]
        
        for filename, data in files:
            filepath = SYNTHETIC_LOGS_DIR / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[OK] {filepath} 저장 완료")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("Synthetic Smartphone Log Generator")
    print("=" * 60)
    
    generator = SyntheticLogGenerator(num_days=NUM_DAYS)
    generator.generate_all()
    generator.save_to_files()
    
    print("\n모든 synthetic data 생성 완료!")


if __name__ == "__main__":
    main()
