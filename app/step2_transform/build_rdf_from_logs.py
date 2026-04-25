"""
Build RDF from Synthetic Logs
JSON 로그 파일을 읽어서 RDF Turtle로 변환

Event-Centric Ontology에 맞춰 변환:
- 각 로그 → Event 엔티티
- User, Person, Place, App도 생성
- Provenance 정보 부착
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# 상위 디렉토리 import를 위한 경로 설정
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.config import (
    SYNTHETIC_LOGS_DIR,
    RDF_OUTPUT_DIR,
    PLACES,
    ensure_directories
)
from app.step2_transform.rdf_utils import (
    RDFBuilder,
    LOG, DATA, RDF, RDFS, PROV,
    create_user_uri,
    create_person_uri,
    create_place_uri,
    create_app_uri,
    create_event_uri,
    create_content_uri,
    get_place_type_class,
    sanitize_id
)


class LogToRDFConverter:
    """로그를 RDF로 변환하는 컨버터"""
    
    def __init__(self):
        self.builder = RDFBuilder()
        
        # 이미 생성된 엔티티 추적 (중복 방지)
        self.created_users = set()
        self.created_persons = set()
        self.created_places = set()
        self.created_apps = set()
    
    def convert_all(self):
        """모든 로그 파일을 RDF로 변환"""
        print("=" * 60)
        print("JSON Logs -> RDF Triples 변환 시작")
        print("=" * 60)
        
        # 1. Call Logs
        self._convert_call_logs()
        
        # 2. App Usage Events
        self._convert_app_usage()
        
        # 3. Calendar Events
        self._convert_calendar_events()
        
        # 4. Visit Events
        self._convert_visit_events()
        
        # 5. Content Metadata
        self._convert_content_metadata()
        
        print(f"\n총 {len(self.builder)} triples 생성 완료")
    
    def _convert_call_logs(self):
        """통화 로그 → CallEvent"""
        filepath = SYNTHETIC_LOGS_DIR / "call_logs.json"
        
        if not filepath.exists():
            print(f"[WARNING] {filepath} 파일이 없습니다")
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            call_logs = json.load(f)
        
        print(f"\n[Call Logs] 변환 중... ({len(call_logs)}건)")
        
        for idx, log in enumerate(call_logs):
            # CallEvent 생성
            call_uri = create_event_uri(log["call_id"])
            self.builder.add_type(call_uri, LOG.CallEvent)
            self.builder.add_label(call_uri, f"{log['callee']}님과의 통화")
            
            # Caller (User)
            caller_uri = create_user_uri(log["caller"])
            self._ensure_user(caller_uri, log["caller"])
            self.builder.add_triple(call_uri, LOG.caller, caller_uri)
            
            # Callee (Person)
            callee_uri = create_person_uri(log["callee"])
            self._ensure_person(callee_uri, log["callee"])
            self.builder.add_triple(call_uri, LOG.callee, callee_uri)
            
            # 시간 정보
            self.builder.add_datetime(call_uri, LOG.startedAt, log["started_at"])
            self.builder.add_integer(call_uri, LOG.durationSeconds, log["duration_seconds"])
            self.builder.add_string(call_uri, LOG.callType, log["call_type"])
            
            # Provenance
            self.builder.add_provenance(call_uri, "call_logs.json", idx)
        
        print(f"   [OK] {len(call_logs)}개 CallEvent 생성")
    
    def _convert_app_usage(self):
        """앱 사용 로그 → AppUsageEvent"""
        filepath = SYNTHETIC_LOGS_DIR / "app_usage.json"
        
        if not filepath.exists():
            print(f"[WARNING] {filepath} 파일이 없습니다")
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            app_events = json.load(f)
        
        print(f"\n[App Usage Events] 변환 중... ({len(app_events)}건)")
        
        for idx, log in enumerate(app_events):
            # AppUsageEvent 생성
            event_uri = create_event_uri(log["app_event_id"])
            self.builder.add_type(event_uri, LOG.AppUsageEvent)
            self.builder.add_label(event_uri, f"{log['app_name']} 사용")
            
            # User
            user_uri = create_user_uri(log["user"])
            self._ensure_user(user_uri, log["user"])
            
            # App
            app_uri = create_app_uri(log["package_name"])
            self._ensure_app(app_uri, log["package_name"], log["app_name"])
            self.builder.add_triple(event_uri, LOG.usedApp, app_uri)
            
            # 이벤트 정보
            self.builder.add_string(event_uri, LOG.appEventType, log["event_type"])
            self.builder.add_datetime(event_uri, LOG.occurredAt, log["occurred_at"])
            self.builder.add_integer(event_uri, LOG.sessionDuration, log["session_duration_seconds"])
            
            # Provenance
            self.builder.add_provenance(event_uri, "app_usage.json", idx)
        
        print(f"   [OK] {len(app_events)}개 AppUsageEvent 생성")
    
    def _convert_calendar_events(self):
        """캘린더 로그 → CalendarEvent"""
        filepath = SYNTHETIC_LOGS_DIR / "calendar_instances.json"
        
        if not filepath.exists():
            print(f"[WARNING] {filepath} 파일이 없습니다")
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            calendar_events = json.load(f)
        
        print(f"\n[Calendar Events] 변환 중... ({len(calendar_events)}건)")
        
        for idx, log in enumerate(calendar_events):
            # CalendarEvent 생성
            event_uri = create_event_uri(log["calendar_event_id"])
            self.builder.add_type(event_uri, LOG.CalendarEvent)
            self.builder.add_string(event_uri, LOG.title, log["title"])
            self.builder.add_label(event_uri, log["title"])
            
            # User
            user_uri = create_user_uri(log["user"])
            self._ensure_user(user_uri, log["user"])
            
            # 시간 정보
            self.builder.add_datetime(event_uri, LOG.startTime, log["start_time"])
            self.builder.add_datetime(event_uri, LOG.endTime, log["end_time"])
            
            # 참석자
            for participant_name in log.get("participants", []):
                participant_uri = create_person_uri(participant_name)
                self._ensure_person(participant_uri, participant_name)
                self.builder.add_triple(event_uri, LOG.participant, participant_uri)
            
            # 카테고리
            self.builder.add_string(event_uri, LOG.category, log["category"])
            
            # Location (텍스트로 저장, 실제 Place 엔티티는 나중에)
            if "location" in log:
                self.builder.add_string(event_uri, RDFS.comment, f"Location: {log['location']}")
            
            # Provenance
            self.builder.add_provenance(event_uri, "calendar_instances.json", idx)
        
        print(f"   [OK] {len(calendar_events)}개 CalendarEvent 생성")
    
    def _convert_visit_events(self):
        """방문 로그 → VisitEvent"""
        filepath = SYNTHETIC_LOGS_DIR / "visit_events.json"
        
        if not filepath.exists():
            print(f"[WARNING] {filepath} 파일이 없습니다")
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            visit_events = json.load(f)
        
        print(f"\n[Visit Events] 변환 중... ({len(visit_events)}건)")
        
        for idx, log in enumerate(visit_events):
            # VisitEvent 생성
            event_uri = create_event_uri(log["visit_event_id"])
            self.builder.add_type(event_uri, LOG.VisitEvent)
            self.builder.add_label(event_uri, f"{log['place_name']} 방문")
            
            # Visitor (User)
            visitor_uri = create_user_uri(log["user"])
            self._ensure_user(visitor_uri, log["user"])
            self.builder.add_triple(event_uri, LOG.visitor, visitor_uri)
            
            # Place
            place_id = sanitize_id(log["place_name"])
            place_uri = create_place_uri(place_id)
            self._ensure_place(place_uri, log["place_name"], log["place_type"], 
                             log.get("lat"), log.get("lng"), log.get("wifi_ssid"))
            self.builder.add_triple(event_uri, LOG.place, place_uri)
            
            # 시간 정보
            self.builder.add_datetime(event_uri, LOG.visitedAt, log["visited_at"])
            
            if log.get("stay_duration_seconds"):
                self.builder.add_integer(event_uri, LOG.stayDuration, log["stay_duration_seconds"])
            
            # WiFi SSID
            if log.get("wifi_ssid"):
                self.builder.add_string(event_uri, LOG.wifiSSID, log["wifi_ssid"])
            
            # Provenance
            self.builder.add_provenance(event_uri, "visit_events.json", idx)
        
        print(f"   [OK] {len(visit_events)}개 VisitEvent 생성")
    
    def _convert_content_metadata(self):
        """콘텐츠 메타데이터 → Content"""
        filepath = SYNTHETIC_LOGS_DIR / "content_metadata.json"
        
        if not filepath.exists():
            print(f"[WARNING] {filepath} 파일이 없습니다")
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            contents = json.load(f)
        
        print(f"\n[Content Metadata] 변환 중... ({len(contents)}건)")
        
        for idx, log in enumerate(contents):
            # Content 생성
            content_uri = create_content_uri(log["content_id"])
            self.builder.add_type(content_uri, LOG.Content)
            self.builder.add_label(content_uri, f"{log['content_type']} - {log.get('place_name', 'Unknown')}")
            
            # Creator (User)
            creator_uri = create_user_uri(log["user"])
            self._ensure_user(creator_uri, log["user"])
            self.builder.add_triple(content_uri, LOG.createdBy, creator_uri)
            
            # 시간 정보
            self.builder.add_datetime(content_uri, LOG.capturedAt, log["captured_at"])
            
            # Content Type
            self.builder.add_string(content_uri, LOG.contentType, log["content_type"])
            
            # File Path
            self.builder.add_string(content_uri, LOG.filePath, log["file_path"])
            
            # Place
            if log.get("place_name"):
                place_id = sanitize_id(log["place_name"])
                place_uri = create_place_uri(place_id)
                self._ensure_place(place_uri, log["place_name"], "unknown",
                                 log.get("lat"), log.get("lng"), None)
                self.builder.add_triple(content_uri, LOG.capturedPlace, place_uri)
            
            # Tags
            if log.get("tags"):
                for tag in log["tags"]:
                    self.builder.add_string(content_uri, RDFS.comment, f"tag: {tag}")
            
            # Provenance
            self.builder.add_provenance(content_uri, "content_metadata.json", idx)
        
        print(f"   [OK] {len(contents)}개 Content 생성")
    
    def _ensure_user(self, user_uri, user_id: str):
        """User 엔티티가 없으면 생성"""
        if user_uri in self.created_users:
            return
        
        self.builder.add_type(user_uri, LOG.User)
        self.builder.add_label(user_uri, "나")
        self.created_users.add(user_uri)
    
    def _ensure_person(self, person_uri, person_name: str):
        """Person 엔티티가 없으면 생성"""
        if person_uri in self.created_persons:
            return
        
        self.builder.add_type(person_uri, LOG.Person)
        self.builder.add_label(person_uri, person_name)
        self.created_persons.add(person_uri)
    
    def _ensure_place(self, place_uri, place_name: str, place_type: str,
                     lat: float = None, lng: float = None, wifi_ssid: str = None):
        """Place 엔티티가 없으면 생성"""
        if place_uri in self.created_places:
            return
        
        # Place 타입에 맞는 클래스 사용
        place_class = get_place_type_class(place_type)
        self.builder.add_type(place_uri, place_class)
        self.builder.add_label(place_uri, place_name)
        self.builder.add_string(place_uri, LOG.placeType, place_type)
        
        if lat is not None:
            self.builder.add_decimal(place_uri, LOG.latitude, lat)
        
        if lng is not None:
            self.builder.add_decimal(place_uri, LOG.longitude, lng)
        
        self.created_places.add(place_uri)
    
    def _ensure_app(self, app_uri, package_name: str, app_name: str):
        """App 엔티티가 없으면 생성"""
        if app_uri in self.created_apps:
            return
        
        self.builder.add_type(app_uri, LOG.App)
        self.builder.add_label(app_uri, app_name)
        self.builder.add_string(app_uri, LOG.packageName, package_name)
        self.created_apps.add(app_uri)
    
    def save(self, output_path: Path = None):
        """RDF를 Turtle 파일로 저장"""
        if output_path is None:
            output_path = RDF_OUTPUT_DIR / "generated_data.ttl"
        
        ensure_directories()
        self.builder.save(str(output_path), format="turtle")
        print(f"\n[SAVE] RDF 파일 저장: {output_path}")
        print(f"   총 {len(self.builder)} triples")


def main():
    """메인 실행 함수"""
    converter = LogToRDFConverter()
    converter.convert_all()
    converter.save()
    
    print("\nRDF 변환 완료!")


if __name__ == "__main__":
    main()
