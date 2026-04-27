from app.agents import llm_client


def test_call_llm_stream_yields_deltas_and_skips_empty(monkeypatch):
    def fake_stream(api_key, full_prompt, temperature):
        yield "안"
        yield ""
        yield "녕"

    monkeypatch.setattr(llm_client, "_get_gemini_keys", lambda: ["key-1"])
    monkeypatch.setattr(llm_client, "_gemini_generate_stream_with_key", fake_stream)
    llm_client._exhausted_keys.clear()

    assert list(llm_client.call_llm_stream("system", "user")) == ["안", "녕"]


def test_call_llm_stream_falls_back_before_first_token(monkeypatch):
    def fake_stream(api_key, full_prompt, temperature):
        raise RuntimeError("temporary failure")
        yield "unreachable"

    monkeypatch.setattr(llm_client, "_get_gemini_keys", lambda: ["key-1"])
    monkeypatch.setattr(llm_client, "_gemini_generate_stream_with_key", fake_stream)
    monkeypatch.setattr(llm_client, "call_llm", lambda **kwargs: "fallback answer")
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
    monkeypatch.setattr(llm_client.time, "sleep", lambda _seconds: None)
    llm_client._gemini_key_index = 0
    llm_client._exhausted_keys.clear()

    assert list(llm_client.call_llm_stream("system", "user")) == ["ok"]
    assert calls == ["key-1", "key-2"]
