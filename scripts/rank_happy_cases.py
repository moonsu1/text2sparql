"""
해피케이스 후보 6개 confidence 일괄 측정
"""
import sys
sys.path.insert(0, "/app")

from app.link_prediction.kg_model_manager import get_model_manager

m = get_model_manager()
m.ensure_ready()

def top(head_uri, rel, filter=None, k=5):
    preds = m.predict(head_uri, rel, top_k=k, node_type_filter=filter)
    return [(u.split("/")[-1], round(c, 3)) for u, c in preds]

print("=" * 60)
print("■ 싱글홉 LP 후보")
print("=" * 60)

# 1. metDuring: 스타벅스 방문에서 누구 만났지?
print("\n[1] visit_012 → metDuring")
print(" ", top("http://example.org/data/visit_012", "metDuring", k=3))

# 2. relatedEvent: 4월17일 투썸 사진 연결된 방문은?
print("\n[2] photo_001 → relatedEvent")
print(" ", top("http://example.org/data/photo_001", "relatedEvent", filter="visit", k=3))

# 3. visitedAfter: Jung Su-jin 통화 후 어디 갔어?
print("\n[3] call_004 → visitedAfter")
print(" ", top("http://example.org/data/call_004", "visitedAfter", filter="visit", k=3))

print()
print("=" * 60)
print("■ 멀티홉 LP 후보")
print("=" * 60)

# 체인1: relatedEvent+metDuring (photo_001 → visit_002 → person)
print("\n[4] CHAIN relatedEvent+metDuring: photo_001→visit_002→?")
r1a = top("http://example.org/data/photo_001", "relatedEvent", filter="visit", k=3)
print("  1hop relatedEvent:", r1a)
r1b = top("http://example.org/data/visit_002", "metDuring", k=3)
print("  2hop metDuring:   ", r1b)

# 체인2: visitedAfter+metDuring (call_004 → visit_012 → person)
print("\n[5] CHAIN visitedAfter+metDuring: call_004→visit_012→?")
r2a = top("http://example.org/data/call_004", "visitedAfter", filter="visit", k=3)
print("  1hop visitedAfter:", r2a)
r2b = top("http://example.org/data/visit_012", "metDuring", k=3)
print("  2hop metDuring:   ", r2b)

# 체인3: relatedEvent+visitedAfter_rev (photo_005 → visit_012 → call?)
print("\n[6] CHAIN relatedEvent+visitedAfter_rev: photo_005→visit_012→call?")
r3a = top("http://example.org/data/photo_005", "relatedEvent", filter="visit", k=3)
print("  1hop relatedEvent:    ", r3a)
r3b = top("http://example.org/data/visit_012", "visitedAfter", filter="call", k=3)
print("  2hop visitedAfter_rev:", r3b)

print()
print("=" * 60)
print("■ 최종 랭킹 (confidence 합계 기준)")
print("=" * 60)

def conf1(lst): return lst[0][1] if lst else 0.0

cases = [
    ("싱글홉", "스타벅스 방문에서 누구?",    conf1(r1b) * 2,   conf1(r1b)),  # reuse visit_012 metDuring
    ("싱글홉", "투썸 사진 연결 방문?",        conf1(r1a) * 2,   conf1(r1a)),
    ("싱글홉", "Jung Su-jin 통화 후 어디?",  conf1(r2a) * 2,   conf1(r2a)),
    ("멀티홉", "투썸 사진→방문→누구?",        conf1(r1a)+conf1(top("http://example.org/data/visit_002","metDuring",k=3)), conf1(r1a)),
    ("멀티홉", "Jung Su-jin 통화→방문→누구?", conf1(r2a)+conf1(r2b), conf1(r2a)),
    ("멀티홉", "스타벅스 사진→통화?",          conf1(r3a)+conf1(r3b), conf1(r3a)),
]

for i, (typ, name, score, c1) in enumerate(sorted(cases, key=lambda x: -x[2]), 1):
    print(f"  {i}위 [{typ}] {name}  합계≈{score:.2f}")
