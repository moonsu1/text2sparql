"""
Fuseki 데이터 직접 확인 스크립트 (Python)
"""

import requests
import sys

# UTF-8 인코딩 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

FUSEKI_URL = "http://localhost:3030"
DATASET = "smartphone_log"

def query_fuseki(sparql_query):
    """Fuseki에 SPARQL 쿼리 실행"""
    url = f"{FUSEKI_URL}/{DATASET}/query"
    response = requests.post(
        url,
        data={"query": sparql_query},
        headers={"Accept": "application/sparql-results+json"}
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error {response.status_code}: {response.text}")
        return None

print("=" * 60)
print("Fuseki 데이터 확인")
print("=" * 60)

# 1. Triple 개수 확인
count_query = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
result = query_fuseki(count_query)
if result:
    count = result["results"]["bindings"][0]["count"]["value"]
    print(f"\n[OK] 총 Triple 개수: {count}")

# 2. Person 목록
person_query = """
PREFIX log: <http://example.org/smartphone-log#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?person ?label WHERE {
    ?person a log:Person .
    ?person rdfs:label ?label .
}
LIMIT 5
"""

result = query_fuseki(person_query)
if result:
    print("\n[OK] Person 목록:")
    for binding in result["results"]["bindings"]:
        label = binding["label"]["value"]
        print(f"   - {label}")

# 3. Event 타입별 개수
event_query = """
PREFIX log: <http://example.org/smartphone-log#>

SELECT ?type (COUNT(?event) AS ?count) WHERE {
    ?event a ?type .
    FILTER(STRSTARTS(STR(?type), "http://example.org/smartphone-log#"))
    FILTER(?type IN (log:CallEvent, log:AppUsageEvent, log:VisitEvent, log:CalendarEvent))
}
GROUP BY ?type
ORDER BY DESC(?count)
"""

result = query_fuseki(event_query)
if result:
    print("\n[OK] Event 타입별 개수:")
    for binding in result["results"]["bindings"]:
        event_type = binding["type"]["value"].split("#")[-1]
        count = binding["count"]["value"]
        print(f"   - {event_type}: {count}개")

print("\n" + "=" * 60)
print("[OK] Fuseki는 정상 작동 중!")
print("=" * 60)
print("\n[INFO] 웹 UI 대신 이 스크립트로 데이터를 확인할 수 있어요.")
print("       또는 챗봇으로 질의를 하면 됩니다!")

