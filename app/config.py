"""
Configuration Management
프로젝트 전체 설정 관리
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent

# Fuseki 설정
FUSEKI_URL = os.getenv("FUSEKI_URL", "http://localhost:3030")
FUSEKI_DATASET = os.getenv("FUSEKI_DATASET", "smartphone_log")

# 데이터 디렉토리
DATA_DIR = PROJECT_ROOT / "data"
SYNTHETIC_LOGS_DIR = DATA_DIR / "synthetic_logs"
RDF_OUTPUT_DIR = DATA_DIR / "rdf"
ONTOLOGY_DIR = DATA_DIR / "ontology"
MAPPINGS_DIR = DATA_DIR / "mappings"

# 생성 설정
NUM_DAYS = int(os.getenv("NUM_DAYS", "7"))
USER_ID = os.getenv("USER_ID", "user_main")

# 네임스페이스
NAMESPACE_LOG = "http://example.org/smartphone-log#"
NAMESPACE_DATA = "http://example.org/data/"

# 주요 연락처
CONTACTS = [
    "Kim Chul-su",
    "Lee Young-hee",
    "Park Min-ji",
    "Choi Dae-han",
    "Jung Su-jin"
]

# 주요 장소
PLACES = [
    {
        "id": "home",
        "name": "우리집",
        "type": "home",
        "wifi": "MyHome_5G",
        "lat": 37.5665,
        "lng": 126.9780
    },
    {
        "id": "office",
        "name": "테크스타트업 오피스",
        "type": "office",
        "wifi": "Company_Guest",
        "lat": 37.4979,
        "lng": 127.0276
    },
    {
        "id": "starbucks_yeoksam",
        "name": "스타벅스 역삼점",
        "type": "cafe",
        "wifi": "Starbucks_WiFi_7429",
        "lat": 37.4979,
        "lng": 127.0276
    },
    {
        "id": "twosome_gangnam",
        "name": "투썸플레이스 강남점",
        "type": "cafe",
        "wifi": "TWOSOME_PLACE",
        "lat": 37.4989,
        "lng": 127.0286
    },
    {
        "id": "salady_yeoksam",
        "name": "샐러디 역삼점",
        "type": "restaurant",
        "wifi": "Salady_Guest",
        "lat": 37.4969,
        "lng": 127.0266
    },
    {
        "id": "mcdonalds_gangnam",
        "name": "맥도날드 강남역점",
        "type": "restaurant",
        "wifi": None,
        "lat": 37.4979,
        "lng": 127.0276
    },
    {
        "id": "gangnam_station",
        "name": "강남역 2호선",
        "type": "station",
        "wifi": "WiFi@Subway",
        "lat": 37.4979,
        "lng": 127.0276
    },
    {
        "id": "coex_mall",
        "name": "코엑스몰",
        "type": "shopping",
        "wifi": "COEX_WiFi",
        "lat": 37.5126,
        "lng": 127.0598
    }
]

# 주요 앱
APPS = [
    {"package": "com.slack", "name": "Slack", "category": "work"},
    {"package": "com.google.gmail", "name": "Gmail", "category": "work"},
    {"package": "com.notion", "name": "Notion", "category": "work"},
    {"package": "com.zoom", "name": "Zoom", "category": "work"},
    {"package": "com.instagram", "name": "Instagram", "category": "social"},
    {"package": "com.kakao.talk", "name": "KakaoTalk", "category": "social"},
    {"package": "com.twitter", "name": "Twitter", "category": "social"},
    {"package": "com.google.youtube", "name": "YouTube", "category": "entertainment"},
    {"package": "com.netflix", "name": "Netflix", "category": "entertainment"},
    {"package": "com.spotify", "name": "Spotify", "category": "entertainment"},
    {"package": "com.google.maps", "name": "Google Maps", "category": "utility"},
    {"package": "com.kakao.map", "name": "카카오맵", "category": "utility"},
    {"package": "com.naver.news", "name": "네이버뉴스", "category": "news"}
]

def ensure_directories():
    """필요한 디렉토리들을 생성"""
    SYNTHETIC_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    RDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ONTOLOGY_DIR.mkdir(parents=True, exist_ok=True)
    MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    ensure_directories()
    print(f"✅ 프로젝트 루트: {PROJECT_ROOT}")
    print(f"✅ Fuseki URL: {FUSEKI_URL}")
    print(f"✅ Dataset: {FUSEKI_DATASET}")
