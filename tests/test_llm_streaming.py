from app.agents import llm_client


def test_call_llm_stream_yields_deltas_and_skips_empty(monkeypatch):
    def fake_stream(api_key, full_prompt, temperature):
        yield "안"
        yield ""
        yield "녕"

    monkeypatch.setattr(llm_client, "_get_gemini_keys", lambda: ["key-1"])
    monkeypatch.setattr(llm_client, "_gemini_generate_stream_with_key", fake_stream)
    monkeypatch.setattr(llm_client, "_get_provider", lambda: "gemini")
    llm_client._exhausted_keys.clear()

    assert list(llm_client.call_llm_stream("system", "user")) == ["안", "녕"]


def test_call_llm_stream_falls_back_before_first_token(monkeypatch):
    def fake_stream(api_key, full_prompt, temperature):
        raise RuntimeError("temporary failure")
        yield "unreachable"

    monkeypatch.setattr(llm_client, "_get_gemini_keys", lambda: ["key-1"])
    monkeypatch.setattr(llm_client, "_gemini_generate_stream_with_key", fake_stream)
    monkeypatch.setattr(llm_client, "_call_gemini", lambda *args, **kwargs: "fallback answer")
    monkeypatch.setattr(llm_client, "_get_provider", lambda: "gemini")
    monkeypatch.setattr(llm_client.time, "sleep", lambda _seconds: None)
    llm_client._exhausted_keys.clear()

    assert list(llm_client.call_llm_stream("system", "user")) == ["fallback answer"]


def test_call_llm_stream_switches_key_on_quota_before_first_token(monkeypatch):
    calls = []

    def fake_stream(api_key, full_prompt, temperature):
        calls.append(api_key)
        if api_key == "key-1":
            raise RuntimeError("429 quota exceeded")
        yield "ok"

    monkeypatch.setattr(llm_client, "_get_gemini_keys", lambda: ["key-1", "key-2"])
    monkeypatch.setattr(llm_client, "_gemini_generate_stream_with_key", fake_stream)
    monkeypatch.setattr(llm_client, "_get_provider", lambda: "gemini")
    monkeypatch.setattr(llm_client.time, "sleep", lambda _seconds: None)
    llm_client._gemini_key_index = 0
    llm_client._exhausted_keys.clear()

    assert list(llm_client.call_llm_stream("system", "user")) == ["ok"]
    assert calls == ["key-1", "key-2"]


def test_call_llm_uses_request_scoped_provider_override(monkeypatch):
    calls = []

    def fake_openai(system_prompt, user_prompt, temperature):
        calls.append("openai")
        return "openai answer"

    def fake_gemini(system_prompt, user_prompt, temperature):
        calls.append("gemini")
        return "gemini answer"

    monkeypatch.setattr(llm_client, "_get_provider", lambda: "gemini")
    monkeypatch.setattr(llm_client, "_call_openai", fake_openai)
    monkeypatch.setattr(llm_client, "_call_gemini", fake_gemini)

    result = llm_client.call_llm(
        "system",
        "user",
        llm_config={"provider": "openai", "model_alias": "kg-openai"},
    )

    assert result == "openai answer"
    assert calls == ["openai"]


def test_call_llm_falls_back_to_default_provider_once_when_override_fails(monkeypatch):
    calls = []

    def fake_openai(system_prompt, user_prompt, temperature):
        calls.append("openai")
        return "[ERROR] missing key"

    def fake_gemini(system_prompt, user_prompt, temperature):
        calls.append("gemini")
        return "gemini answer"

    monkeypatch.setattr(llm_client, "_get_provider", lambda: "gemini")
    monkeypatch.setattr(llm_client, "_call_openai", fake_openai)
    monkeypatch.setattr(llm_client, "_call_gemini", fake_gemini)

    result = llm_client.call_llm(
        "system",
        "user",
        llm_config={"provider": "openai", "model_alias": "kg-openai"},
    )

    assert result == "gemini answer"
    assert calls == ["openai", "gemini"]


def test_call_llm_stream_falls_back_to_default_provider_before_first_token_for_override(monkeypatch):
    calls = []

    def fake_openai_stream(system_prompt, user_prompt, temperature):
        calls.append("openai")
        yield "[ERROR] missing key"

    def fake_gemini_stream(system_prompt, user_prompt, temperature):
        calls.append("gemini")
        yield "fallback answer"

    monkeypatch.setattr(llm_client, "_get_provider", lambda: "gemini")
    monkeypatch.setattr(llm_client, "_call_openai_stream", fake_openai_stream)
    monkeypatch.setattr(llm_client, "_call_gemini_stream", fake_gemini_stream)

    chunks = list(
        llm_client.call_llm_stream(
            "system",
            "user",
            llm_config={"provider": "openai", "model_alias": "kg-openai"},
        )
    )

    assert chunks == ["fallback answer"]
    assert calls == ["openai", "gemini"]


def test_call_llm_stream_does_not_fallback_after_partial_output(monkeypatch):
    calls = []

    def fake_openai_stream(system_prompt, user_prompt, temperature):
        calls.append("openai")
        yield "partial"
        yield "[ERROR] interrupted"

    def fake_gemini_stream(system_prompt, user_prompt, temperature):
        calls.append("gemini")
        yield "fallback answer"

    monkeypatch.setattr(llm_client, "_get_provider", lambda: "gemini")
    monkeypatch.setattr(llm_client, "_call_openai_stream", fake_openai_stream)
    monkeypatch.setattr(llm_client, "_call_gemini_stream", fake_gemini_stream)

    chunks = list(
        llm_client.call_llm_stream(
            "system",
            "user",
            llm_config={"provider": "openai", "model_alias": "kg-openai"},
        )
    )

    assert chunks == ["partial", "[ERROR] interrupted"]
    assert calls == ["openai"]
