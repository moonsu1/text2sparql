import sys; sys.path.insert(0, "/app")
from app.link_prediction.kg_model_manager import get_model_manager
m = get_model_manager(); m.ensure_ready()

def top(h, rel, f=None, k=3):
    preds = m.predict(h, rel, top_k=k, node_type_filter=f)
    return [(u.split("/")[-1], round(c,3)) for u,c in preds]

# chain4: visitedAfter+relatedEvent_rev (통화→방문←사진)
print("[chain4] call_001 → visitedAfter → visit_002 → relatedEvent_rev → photo?")
a = top("http://example.org/data/call_001", "visitedAfter", "visit", 3)
print("  1hop visitedAfter:", a)
b = top("http://example.org/data/visit_002", "relatedEvent", "photo", 3)
print("  2hop relatedEvent(rev):", b)

print()
print("[chain4] call_004 → visitedAfter → visit_012 → relatedEvent_rev → photo?")
c = top("http://example.org/data/call_004", "visitedAfter", "visit", 3)
print("  1hop visitedAfter:", c)
d = top("http://example.org/data/visit_012", "relatedEvent", "photo", 3)
print("  2hop relatedEvent(rev):", d)

print()
# chain3 with call_001: visitedAfter_rev from visit_002
print("[chain3_fix] call before visit_002: predict (visit_002, visitedAfter, 'call')")
e = top("http://example.org/data/visit_002", "visitedAfter", "call", 3)
print("  visitedAfter_rev from visit_002:", e)
