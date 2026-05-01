from app.link_prediction.kg_model_manager import get_model_manager
m = get_model_manager()
m.ensure_ready()

tests = [
    ("http://example.org/data/visit_002", "metDuring"),
    ("http://example.org/data/visit_012", "metDuring"),
    ("http://example.org/data/photo_005", "relatedEvent"),
    ("http://example.org/data/call_004",  "visitedAfter"),
]
for head_uri, rel in tests:
    preds = m.predict(head_uri, rel, top_k=5, node_type_filter=None)
    h = head_uri.split("/")[-1]
    print(f"\n[{rel}] {h}:")
    for uri, c in preds:
        node = uri.split("/")[-1]
        print(f"  {node}: {c:.3f}")
