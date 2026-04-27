"""
LLM Client - Multi-Provider (Gemini / Ollama)

LLM_PROVIDER=gemini  → Gemini API (기본)
LLM_PROVIDER=ollama  → Ollama /api/chat (Qwen 등 로컬 모델)
"""

import os
import time
import re
import json
import requests
from typing import Iterator
from dotenv import load_dotenv

load_dotenv()

# ── Gemini 상태 ────────────────────────────────────────────
_gemini_key_index = 0
_exhausted_keys: dict = {}


# ═══════════════════════════════════════════════════════════
# Provider 선택
# ═══════════════════════════════════════════════════════════

def _get_provider() -> str:
    """현재 LLM_PROVIDER 반환 ('gemini' 또는 'ollama')"""
    return os.getenv("LLM_PROVIDER", "gemini").strip().lower()


def _get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen3.5:4b")


def _get_ollama_num_predict() -> int:
    return int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))


# ═══════════════════════════════════════════════════════════
# Ollama 구현
# ═══════════════════════════════════════════════════════════

def _call_ollama(system_prompt: str, user_prompt: str, temperature: float) -> str:
    """
    Ollama /api/chat (blocking) 호출.

    Qwen3.5는 thinking 모델이라 reasoning에 토큰을 먼저 소비한다.
    - think=false 옵션으로 reasoning을 억제한다.
    - 그래도 content가 비면 reasoning 필드를 content로 대체한다.
    """
    base_url = _get_ollama_base_url()
    model = _get_ollama_model()
    num_predict = _get_ollama_num_predict()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }

    try:
        resp = requests.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        message = data.get("message", {})
        content = message.get("content", "").strip()

        # content가 비면 reasoning 필드로 대체 (Qwen thinking fallback)
        if not content:
            reasoning = message.get("reasoning", "").strip()
            if reasoning:
                print("  [ollama] content 비어 reasoning fallback 사용")
                content = reasoning

        if not content:
            print(f"  [ollama] 빈 응답 (model={model})")
            return "[ERROR] Ollama 빈 응답"

        return content

    except requests.exceptions.ConnectionError:
        msg = f"Ollama 서버에 연결할 수 없습니다 ({base_url}). Ollama가 실행 중인지 확인하세요."
        print(f"  [ollama] {msg}")
        return f"[ERROR] {msg}"
    except requests.exceptions.Timeout:
        print(f"  [ollama] 응답 타임아웃 (120s)")
        return "[ERROR] Ollama 응답 타임아웃"
    except Exception as e:
        print(f"  [ollama] 호출 실패: {str(e)[:120]}")
        return f"[ERROR] Ollama 호출 실패: {str(e)[:80]}"


def _call_ollama_stream(
    system_prompt: str, user_prompt: str, temperature: float
) -> Iterator[str]:
    """
    Ollama /api/chat (streaming) 호출.
    JSONL 응답에서 message.content 토큰만 yield.
    """
    base_url = _get_ollama_base_url()
    model = _get_ollama_model()
    num_predict = _get_ollama_num_predict()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }

    try:
        with requests.post(
            f"{base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()

            yielded_any = False
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                try:
                    chunk = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                delta = chunk.get("message", {}).get("content", "")
                if delta:
                    yielded_any = True
                    yield delta

                if chunk.get("done", False):
                    break

            if not yielded_any:
                print(f"  [ollama-stream] 스트리밍에서 아무 토큰도 받지 못함")
                yield "[ERROR] Ollama 스트리밍 빈 응답"

    except requests.exceptions.ConnectionError:
        msg = f"Ollama 서버 연결 실패 ({base_url})"
        print(f"  [ollama-stream] {msg}")
        yield f"[ERROR] {msg}"
    except requests.exceptions.Timeout:
        print("  [ollama-stream] 타임아웃")
        yield "[ERROR] Ollama 스트리밍 타임아웃"
    except Exception as e:
        print(f"  [ollama-stream] 실패: {str(e)[:120]}")
        yield f"[ERROR] Ollama 스트리밍 실패: {str(e)[:80]}"


# ═══════════════════════════════════════════════════════════
# Gemini 구현 (기존 코드 보존)
# ═══════════════════════════════════════════════════════════

def _get_gemini_keys() -> list[str]:
    """GEMINI_API_KEYS에서 키 목록 반환"""
    keys_str = os.getenv("GEMINI_API_KEYS", "").strip()
    if keys_str:
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if keys:
            return keys
    single = os.getenv("GEMINI_API_KEY", "").strip()
    if single:
        return [single]
    return []


def _is_key_exhausted(key_index: int, cooldown_seconds: int = 10) -> bool:
    if key_index not in _exhausted_keys:
        return False
    elapsed = time.time() - _exhausted_keys[key_index]
    if elapsed < cooldown_seconds:
        return True
    del _exhausted_keys[key_index]
    return False


def _mark_key_exhausted(key_index: int):
    _exhausted_keys[key_index] = time.time()
    print(f"  [gemini] 키 #{key_index+1} 쿼터 소진 (10초간 스킵)")


def _gemini_generate_with_key(api_key: str, full_prompt: str, temperature: float) -> str:
    import google.generativeai as genai
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        full_prompt,
        generation_config={"temperature": temperature, "max_output_tokens": 4096},
    )
    return response.text


def _gemini_generate_stream_with_key(
    api_key: str, full_prompt: str, temperature: float
) -> Iterator[str]:
    import google.generativeai as genai
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        full_prompt,
        generation_config={"temperature": temperature, "max_output_tokens": 4096},
        stream=True,
    )
    for chunk in response:
        try:
            text = chunk.text or ""
        except Exception:
            text = ""
        if text:
            yield text


def _is_quota_error(err_str: str) -> bool:
    return "429" in err_str or "quota" in err_str.lower() or "ResourceExhausted" in err_str


def _call_gemini(system_prompt: str, user_prompt: str, temperature: float) -> str:
    global _gemini_key_index
    keys = _get_gemini_keys()
    if not keys:
        return "[ERROR] GEMINI_API_KEYS를 .env에 설정해주세요"

    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    n_keys = len(keys)

    available_keys = [i for i in range(n_keys) if not _is_key_exhausted(i)]
    if not available_keys:
        print("  [gemini] 모든 키 소진, 10초 대기 후 재시도...")
        time.sleep(10)
        _exhausted_keys.clear()
        available_keys = list(range(n_keys))

    start_index = _gemini_key_index
    for _ in range(len(available_keys)):
        attempts = 0
        while attempts < n_keys:
            current_index = (start_index + attempts) % n_keys
            if not _is_key_exhausted(current_index):
                break
            attempts += 1
        else:
            print("  [gemini] 모든 키 소진, 10초 대기...")
            time.sleep(10)
            _exhausted_keys.clear()
            current_index = start_index

        api_key = keys[current_index]
        key_num = current_index + 1

        try:
            result = _gemini_generate_with_key(api_key, full_prompt, temperature)
            _gemini_key_index = (current_index + 1) % n_keys
            if current_index != start_index % n_keys:
                print(f"  [gemini] 키 #{key_num}로 성공")
            return result

        except Exception as e:
            err_str = str(e)
            if _is_quota_error(err_str):
                _mark_key_exhausted(current_index)
                start_index = current_index + 1
                time.sleep(0.2)
                continue
            else:
                print(f"  [gemini] 호출 실패 (키 #{key_num}): {err_str[:100]}")
                time.sleep(2)

    print("  [gemini] 최종 실패 (모든 재시도 소진)")
    return "[ERROR] LLM 호출 실패 - 재시도 초과"


def _call_gemini_stream(
    system_prompt: str, user_prompt: str, temperature: float
) -> Iterator[str]:
    global _gemini_key_index
    keys = _get_gemini_keys()
    if not keys:
        yield "[ERROR] GEMINI_API_KEYS를 .env에 설정해주세요"
        return

    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    n_keys = len(keys)
    available_keys = [i for i in range(n_keys) if not _is_key_exhausted(i)]

    if not available_keys:
        print("  [gemini] 모든 키 소진, 10초 대기 후 재시도...")
        time.sleep(10)
        _exhausted_keys.clear()
        available_keys = list(range(n_keys))

    start_index = _gemini_key_index
    yielded_any = False

    for _ in range(len(available_keys)):
        attempts = 0
        while attempts < n_keys:
            current_index = (start_index + attempts) % n_keys
            if not _is_key_exhausted(current_index):
                break
            attempts += 1
        else:
            print("  [gemini] 모든 키 소진, 10초 대기...")
            time.sleep(10)
            _exhausted_keys.clear()
            current_index = start_index % n_keys

        api_key = keys[current_index]
        key_num = current_index + 1

        try:
            for delta in _gemini_generate_stream_with_key(api_key, full_prompt, temperature):
                if not delta:
                    continue
                yielded_any = True
                yield delta

            if yielded_any:
                _gemini_key_index = (current_index + 1) % n_keys
                if current_index != start_index % n_keys:
                    print(f"  [gemini] 키 #{key_num} streaming 성공")
                return

            print(f"  [gemini] streaming 빈 응답 (키 #{key_num})")
            break

        except Exception as e:
            err_str = str(e)
            if yielded_any:
                print(f"  [gemini] streaming 중단 (키 #{key_num}): {err_str[:100]}")
                yield "\n\n[ERROR] 답변 생성 중 스트리밍이 중단되었습니다."
                return
            if _is_quota_error(err_str):
                _mark_key_exhausted(current_index)
                start_index = current_index + 1
                time.sleep(0.2)
                continue
            print(f"  [gemini] streaming 실패 (키 #{key_num}): {err_str[:100]}")
            time.sleep(2)

    if yielded_any:
        return

    print("  [gemini] streaming 실패, blocking fallback")
    yield _call_gemini(system_prompt, user_prompt, temperature)


# ═══════════════════════════════════════════════════════════
# 공개 인터페이스 (기존 호출 코드 변경 없음)
# ═══════════════════════════════════════════════════════════

def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = None,
    max_retries: int = None,
) -> str:
    """
    LLM 호출 (blocking).
    LLM_PROVIDER 환경변수로 Gemini / Ollama 선택.
    """
    if temperature is None:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    provider = _get_provider()
    print(f"  [llm] provider={provider}", end="")

    if provider in ("ollama", "qwen", "local"):
        print(f" model={_get_ollama_model()}")
        return _call_ollama(system_prompt, user_prompt, temperature)

    print(f" model={os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}")
    return _call_gemini(system_prompt, user_prompt, temperature)


def call_llm_stream(
    system_prompt: str,
    user_prompt: str,
    temperature: float = None,
    max_retries: int = None,
) -> Iterator[str]:
    """
    LLM 스트리밍 호출.
    LLM_PROVIDER 환경변수로 Gemini / Ollama 선택.
    """
    if temperature is None:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    provider = _get_provider()

    if provider in ("ollama", "qwen", "local"):
        yield from _call_ollama_stream(system_prompt, user_prompt, temperature)
        return

    yield from _call_gemini_stream(system_prompt, user_prompt, temperature)
