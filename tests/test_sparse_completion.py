from backend.openai_compat import (
    ChatCompletionRequest,
    Message,
    _request_use_link_prediction,
    format_agent_event_for_markdown,
)
from app.agents.tools import link_prediction_tools as lpt
from app.agents.tools.sparql_tools import generate_sparql


def _request(value=None):
    payload = {
        "model": "rdf-kg-agent",
        "messages": [Message(role="user", content="test")],
    }
    if value is not None:
        payload["use_link_prediction"] = value
    return ChatCompletionRequest(**payload)


def test_openai_link_prediction_defaults_to_true_and_can_be_disabled():
    assert _request_use_link_prediction(_request()) is True
    assert _request_use_link_prediction(_request(False)) is False
    assert _request_use_link_prediction(_request(True)) is True


def test_relation_predictors_use_current_ontology_predicates(monkeypatch):
    calls = []

    rows_by_relation = {
        "visitedAfter": [
            {
                "call": "http://example.org/data/call_004",
                "person": "http://example.org/data/JungSujin",
                "personLabel": "Jung Su-jin",
                "callTime": "2026-04-21T11:27:00",
                "visit": "http://example.org/data/visit_012",
                "visitTime": "2026-04-21T11:53:00",
                "place": "http://example.org/data/starbucks",
                "placeLabel": "스타벅스 역삼점",
                "placeType": "cafe",
            }
        ],
        "metDuring": [
            {
                "visit": "http://example.org/data/visit_012",
                "visitTime": "2026-04-21T11:53:00",
                "place": "http://example.org/data/starbucks",
                "placeLabel": "스타벅스 역삼점",
                "placeType": "cafe",
                "call": "http://example.org/data/call_004",
                "callTime": "2026-04-21T11:27:00",
                "person": "http://example.org/data/JungSujin",
                "personLabel": "Jung Su-jin",
            }
        ],
        "relatedEvent": [
            {
                "content": "http://example.org/data/photo_005",
                "contentLabel": "photo - 스타벅스 역삼점",
                "contentType": "photo",
                "capturedAt": "2026-04-21T11:58:00",
                "visit": "http://example.org/data/visit_012",
                "visitTime": "2026-04-21T11:53:00",
                "place": "http://example.org/data/starbucks",
                "placeLabel": "스타벅스 역삼점",
                "placeType": "cafe",
            }
        ],
        "usedDuring": [
            {
                "appEvent": "http://example.org/data/app_evt_012",
                "appTime": "2026-04-21T08:56:00",
                "app": "http://example.org/data/app_notion",
                "appLabel": "Notion",
                "calendar": "http://example.org/data/cal_002",
                "title": "디자인 리뷰",
                "startTime": "2026-04-21T10:00:00",
                "category": "work",
            }
        ],
    }

    def fake_execute(sparql):
        calls.append(sparql)
        relation = current_relation["name"]
        return rows_by_relation[relation]

    monkeypatch.setattr(lpt, "_execute_select", fake_execute)

    current_relation = {"name": "visitedAfter"}
    for relation in rows_by_relation:
        current_relation["name"] = relation
        result = lpt.predict_sparse_relations(
            {
                "query": "4월 21일 스타벅스 디자인 리뷰",
                "target_relation": relation,
                "entities": {
                    "person": "Jung Su",
                    "place_type": "cafe",
                    "place_mention": "스타벅스",
                    "event_title": "디자인 리뷰",
                },
                "resolved_entities": {
                    "person": {"label": "Jung Su-jin", "search_name": "Jung Su"}
                },
            }
        )
        assert result["predictions"]

    combined = "\n".join(calls)
    assert "log:calledPerson" not in combined
    assert "log:visitedPlace" not in combined
    for predicate in [
        "log:callee",
        "log:startedAt",
        "log:place",
        "log:visitedAt",
        "log:capturedPlace",
        "log:capturedAt",
        "log:usedApp",
        "log:occurredAt",
        "log:startTime",
    ]:
        assert predicate in combined


def test_confidence_threshold_filters_weak_candidates(monkeypatch):
    monkeypatch.setattr(
        lpt,
        "_execute_select",
        lambda _sparql: [
            {
                "call": "http://example.org/data/call_004",
                "person": "http://example.org/data/JungSujin",
                "personLabel": "Jung Su-jin",
                "callTime": "2026-04-21T09:00:00",
                "visit": "http://example.org/data/visit_012",
                "visitTime": "2026-04-21T13:00:00",
                "place": "http://example.org/data/starbucks",
                "placeLabel": "스타벅스 역삼점",
                "placeType": "cafe",
            }
        ],
    )

    result = lpt.predict_sparse_relations(
        {
            "query": "Jung Su-jin이랑 통화하고 나서 들른 카페 어디였지?",
            "target_relation": "visitedAfter",
            "entities": {"person": "Jung Su", "place_type": "cafe"},
            "resolved_entities": {"person": {"label": "Jung Su-jin", "search_name": "Jung Su"}},
        }
    )

    assert result["predictions"] == []


def test_formatter_outputs_prediction_evidence_once():
    event = {
        "type": "stage_complete",
        "stage": "link_prediction",
        "state": {
            "predicted_triples": [
                (
                    "http://example.org/data/call_004",
                    "http://example.org/smartphone-log#visitedAfter",
                    "http://example.org/data/visit_012",
                )
            ],
            "prediction_evidence": [
                {
                    "head": "http://example.org/data/call_004",
                    "relation": "http://example.org/smartphone-log#visitedAfter",
                    "tail": "http://example.org/data/visit_012",
                    "relation_label": "visitedAfter",
                    "confidence": 0.90,
                    "evidence": "통화 후 26분 뒤 같은 생활권 카페 방문",
                }
            ],
        },
    }

    text = format_agent_event_for_markdown(event)

    assert text.count("예측된 관계") == 1
    assert "call_004" in text
    assert "log:visitedAfter" in text
    assert "통화 후 26분" in text


def test_predicted_sparql_uses_values_not_persistent_edges():
    sparql = generate_sparql(
        query="Jung Su-jin이랑 통화하고 나서 들른 카페 어디였지?",
        intent="sparse_completion",
        entities_text="person: Jung Su-jin",
        time_info="없음",
        predicted_triples=[
            (
                "http://example.org/data/call_004",
                "http://example.org/smartphone-log#visitedAfter",
                "http://example.org/data/visit_012",
            )
        ],
        prediction_confidence=[0.90],
        prediction_evidence=[
            {
                "head": "http://example.org/data/call_004",
                "relation": "http://example.org/smartphone-log#visitedAfter",
                "tail": "http://example.org/data/visit_012",
                "confidence": 0.90,
                "evidence": "통화 후 26분 뒤 같은 생활권 카페 방문",
            }
        ],
        target_relation="visitedAfter",
    )

    assert "VALUES (?call ?visit ?confidence ?evidence)" in sparql
    assert "log:visitedAfter" not in sparql
    assert "log:callee" in sparql
    assert "log:startedAt" in sparql
    assert "log:place" in sparql
    assert "log:visitedAt" in sparql
