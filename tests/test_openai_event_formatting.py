from backend.openai_compat import format_agent_event_for_markdown


def _render_events(events):
    supervisor_index = 0
    chunks = []

    for event in events:
        if event.get("type") == "supervisor_decision":
            supervisor_index += 1

        text = format_agent_event_for_markdown(event, supervisor_index)
        if text:
            chunks.append(text)

    return "".join(chunks)


def test_supervisor_decision_precedes_stage_output():
    text = _render_events([
        {"type": "stage_start", "stage": "query_analysis"},
        {
            "type": "stage_complete",
            "stage": "query_analysis",
            "state": {
                "intent": "recent_calls",
                "entities": {"person": "Kim Chul"},
                "time_constraint": None,
            },
        },
        {
            "type": "supervisor_decision",
            "stage": "supervisor",
            "next_stage": "sparql_generation",
            "reasoning": "**[1단계]** SPARQL 쿼리를 생성합니다.",
        },
        {
            "type": "stage_complete",
            "stage": "sparql_generation",
            "state": {"sparql_query": "SELECT ?s WHERE { ?s ?p ?o }"},
        },
    ])

    assert text.index("[Supervisor]") < text.index("**SPARQL 생성**")
    assert "Supervisor [1단계]" not in text
    assert "처리 과정" not in text
    assert "<small>" not in text
    assert "<div>" not in text
    assert text.index("**SPARQL 생성**") < text.index("```sparql")


def test_interleaved_stream_does_not_duplicate_sparql_or_answer():
    text = _render_events([
        {
            "type": "supervisor_decision",
            "stage": "supervisor",
            "next_stage": "sparql_generation",
            "reasoning": "**[1단계]** SPARQL 쿼리를 생성합니다.",
        },
        {
            "type": "stage_complete",
            "stage": "sparql_generation",
            "state": {"sparql_query": "SELECT ?s WHERE { ?s ?p ?o }"},
        },
        {
            "type": "supervisor_decision",
            "stage": "supervisor",
            "next_stage": "execution",
            "reasoning": "**[2단계]** 쿼리를 실행합니다.",
        },
        {
            "type": "stage_complete",
            "stage": "execution",
            "state": {
                "sparql_results": [{"s": "data:call_001"}],
                "execution_time_ms": 12.34,
            },
        },
        {
            "type": "supervisor_decision",
            "stage": "supervisor",
            "next_stage": "answer",
            "reasoning": "**[3단계]** 최종 답변을 생성합니다.",
        },
        {
            "type": "stage_complete",
            "stage": "answer",
            "state": {"answer": "최종 답변입니다."},
        },
        {"type": "final", "stage": "END", "result": {"answer": "최종 답변입니다."}},
    ])

    assert text.index("[Supervisor]") < text.index("실행 결과")
    assert text.count("[Supervisor]") == 3
    assert text.count("## 최종 답변") == 1
    assert text.count("SELECT ?s WHERE") == 1
    assert text.count("최종 답변입니다.") == 1


def test_streaming_answer_tokens_render_without_duplicate_answer():
    text = _render_events([
        {
            "type": "supervisor_decision",
            "stage": "supervisor",
            "next_stage": "answer",
            "reasoning": "**[1단계]** 최종 답변을 생성합니다.",
        },
        {"type": "stage_start", "stage": "answer"},
        {"type": "answer_token", "stage": "answer", "delta": "안녕하세요"},
        {"type": "answer_token", "stage": "answer", "delta": "!"},
        {
            "type": "stage_complete",
            "stage": "answer",
            "state": {
                "answer": "안녕하세요!",
                "answer_streamed": True,
            },
        },
        {"type": "final", "stage": "END", "result": {"answer": "안녕하세요!"}},
    ])

    assert text.count("## 최종 답변") == 1
    assert text.count("안녕하세요!") == 1
    assert text.endswith("안녕하세요!")


def test_stage_start_outputs_progress_line():
    text = _render_events([
        {"type": "stage_start", "stage": "sparql_generation"},
    ])

    assert "SPARQL을 생성하는 중입니다" in text
