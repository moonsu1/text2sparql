"""KG 데이터 통계 및 예측 가능 시나리오 분석"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.agents.tools.link_prediction_tools import _execute_select, LOG

print("=" * 60)
print("1. 관계별 트리플 수")
print("=" * 60)
rows = _execute_select(
    f'PREFIX log: <{LOG}> '
    f'SELECT ?rel (COUNT(*) as ?cnt) WHERE {{ '
    f'?s ?rel ?o . FILTER(STRSTARTS(STR(?rel), "{LOG}")) '
    f'}} GROUP BY ?rel ORDER BY DESC(?cnt)'
)
for r in rows:
    rel = r.get('rel', '').split('#')[-1]
    print(f"  {rel}: {r.get('cnt', '?')}")

print()
print("=" * 60)
print("2. CallEvent 목록 (통화 이벤트)")
print("=" * 60)
rows = _execute_select(
    f'PREFIX log: <{LOG}> '
    f'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> '
    f'SELECT ?call ?personLabel ?callTime WHERE {{ '
    f'?call a log:CallEvent ; log:callee ?person ; log:startedAt ?callTime . '
    f'?person rdfs:label ?personLabel . '
    f'}} ORDER BY ?callTime'
)
for r in rows:
    call_id = r.get('call', '').split('/')[-1]
    print(f"  {call_id}: {r.get('personLabel','?')} at {r.get('callTime','?')}")

print()
print("=" * 60)
print("3. VisitEvent 목록")
print("=" * 60)
rows = _execute_select(
    f'PREFIX log: <{LOG}> '
    f'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> '
    f'SELECT ?visit ?placeLabel ?visitTime WHERE {{ '
    f'?visit a log:VisitEvent ; log:place ?place ; log:visitedAt ?visitTime . '
    f'?place rdfs:label ?placeLabel . '
    f'}} ORDER BY ?visitTime'
)
for r in rows:
    visit_id = r.get('visit', '').split('/')[-1]
    print(f"  {visit_id}: {r.get('placeLabel','?')} at {r.get('visitTime','?')}")

print()
print("=" * 60)
print("4. Content (사진) 목록")
print("=" * 60)
rows = _execute_select(
    f'PREFIX log: <{LOG}> '
    f'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> '
    f'SELECT ?content ?contentLabel ?capturedAt ?placeLabel WHERE {{ '
    f'?content a log:Content ; rdfs:label ?contentLabel ; log:capturedAt ?capturedAt . '
    f'OPTIONAL {{ ?content log:capturedPlace ?cp . ?cp rdfs:label ?placeLabel . }} '
    f'}} ORDER BY ?capturedAt'
)
for r in rows:
    cid = r.get('content', '').split('/')[-1]
    print(f"  {cid}: {r.get('contentLabel','?')} at {r.get('capturedAt','?')} [{r.get('placeLabel','?')}]")

print()
print("=" * 60)
print("5. 실제 존재하는 sparse 관계 트리플")
print("=" * 60)
for rel in ['visitedAfter', 'metDuring', 'relatedEvent', 'usedDuring']:
    rows = _execute_select(
        f'PREFIX log: <{LOG}> '
        f'SELECT ?h ?t WHERE {{ ?h log:{rel} ?t . }}'
    )
    if rows:
        for r in rows:
            h = r.get('h','').split('/')[-1]
            t = r.get('t','').split('/')[-1]
            print(f"  [{rel}] {h} → {t}")
    else:
        print(f"  [{rel}] 없음 (sparse)")
