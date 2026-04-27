from app.agents import kg_agent_supervisor as supervisor_module
from app.agents.kg_agent_supervisor import KGAgentSupervisor


class FakeCompiledGraph:
    def stream(self, initial_state, stream_mode):
        assert stream_mode == "updates"

        yield {
            "supervisor": {
                "workflow_path": ["supervisor"],
                "current_stage": "sparql_generation",
                "supervisor_reasoning_log": ["**[1단계]** SPARQL 쿼리를 생성합니다."],
            }
        }

        yield {
            "sparql_generation": {
                "workflow_path": ["sparql_generation"],
                "sparql_query": "SELECT ?s WHERE { ?s ?p ?o }",
            }
        }


class FakeAnswerCompiledGraph:
    def stream(self, initial_state, stream_mode):
        assert stream_mode == "updates"

        yield {
            "supervisor": {
                "workflow_path": ["supervisor"],
                "current_stage": "answer",
                "supervisor_reasoning_log": ["**[1단계]** 최종 답변을 생성합니다."],
                "sparql_results": [{"event": "http://example.org/data/call_001"}],
            }
        }


def test_stream_query_events_emits_decision_before_stage_complete(monkeypatch):
    def fake_query_analysis_stage(state):
        return {
            "intent": "recent_calls",
            "entities": {},
            "time_constraint": None,
            "workflow_path": ["query_analysis"],
            "resolved_entities": {},
            "sparql_results": None,
            "link_prediction_done": False,
            "sparql_retry_count": 0,
        }

    monkeypatch.setattr(
        supervisor_module,
        "query_analysis_stage",
        fake_query_analysis_stage,
    )

    agent = KGAgentSupervisor.__new__(KGAgentSupervisor)
    agent.app = FakeCompiledGraph()

    events = list(agent.stream_query_events("최근 통화한 사람은 누구야?"))
    event_keys = [
        (event.get("type"), event.get("stage"), event.get("next_stage"))
        for event in events
    ]

    assert event_keys[:5] == [
        ("stage_start", "query_analysis", None),
        ("stage_complete", "query_analysis", None),
        ("supervisor_decision", "supervisor", "sparql_generation"),
        ("stage_start", "sparql_generation", None),
        ("stage_complete", "sparql_generation", None),
    ]
    assert events[-1]["type"] == "final"
    assert events[-1]["result"]["sparql_query"] == "SELECT ?s WHERE { ?s ?p ?o }"


def test_stream_query_events_streams_answer_tokens(monkeypatch):
    def fake_query_analysis_stage(state):
        return {
            "intent": "recent_calls",
            "entities": {},
            "time_constraint": None,
            "workflow_path": ["query_analysis"],
            "resolved_entities": {},
            "sparql_results": [{"event": "http://example.org/data/call_001"}],
            "link_prediction_done": False,
            "sparql_retry_count": 0,
        }

    monkeypatch.setattr(
        supervisor_module,
        "query_analysis_stage",
        fake_query_analysis_stage,
    )
    monkeypatch.setattr(
        supervisor_module,
        "build_answer_generation_prompt",
        lambda state: ("system", "user"),
    )
    monkeypatch.setattr(
        supervisor_module,
        "call_llm_stream",
        lambda **kwargs: iter(["안녕하세요", "!"]),
    )

    agent = KGAgentSupervisor.__new__(KGAgentSupervisor)
    agent.app = FakeAnswerCompiledGraph()

    events = list(agent.stream_query_events("답변 테스트"))
    event_keys = [
        (event.get("type"), event.get("stage"), event.get("next_stage"))
        for event in events
    ]

    assert event_keys[:6] == [
        ("stage_start", "query_analysis", None),
        ("stage_complete", "query_analysis", None),
        ("supervisor_decision", "supervisor", "answer"),
        ("stage_start", "answer", None),
        ("answer_token", "answer", None),
        ("answer_token", "answer", None),
    ]
    assert event_keys[6] == ("stage_complete", "answer", None)
    assert events[6]["state"]["answer_streamed"] is True
    assert events[-1]["type"] == "final"
    assert events[-1]["result"]["answer"] == "안녕하세요!"
    assert events[-1]["result"]["sources"] == ["call_001"]
