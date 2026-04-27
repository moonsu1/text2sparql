"""
LLM Client (Gemini)
ai_daily_briefing 구조를 참고하여 구현
"""

import os
import time
import re
from typing import Iterator
from dotenv import load_dotenv

load_dotenv()

# 라운드로빈 키 인덱스
_gemini_key_index = 0

# 쿼터 소진된 키 캐시 (키 인덱스 → 소진 시각)
_exhausted_keys = {}


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
    """키가 쿼터 소진 상태인지 확인 (캐시 기반)"""
    if key_index not in _exhausted_keys:
        return False
    
    exhausted_at = _exhausted_keys[key_index]
    elapsed = time.time() - exhausted_at
    
    if elapsed < cooldown_seconds:
        return True
    else:
        # Cooldown 지났으면 캐시에서 제거
        del _exhausted_keys[key_index]
        return False


def _mark_key_exhausted(key_index: int):
    """키를 쿼터 소진 상태로 마크"""
    _exhausted_keys[key_index] = time.time()
    print(f"  [llm] ⚠️ 키 #{key_index+1} 쿼터 소진 (10초간 스킵)")


def _gemini_generate_with_key(api_key: str, full_prompt: str, temperature: float) -> str:
    """지정한 API 키로 Gemini 호출"""
    import google.generativeai as genai
    
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    response = model.generate_content(
        full_prompt,
        generation_config={
            "temperature": temperature,
            "max_output_tokens": 4096,
        },
    )
    return response.text


def _extract_stream_chunk_text(chunk) -> str:
    """Gemini streaming chunk에서 안전하게 텍스트 delta를 추출."""
    try:
        return chunk.text or ""
    except Exception:
        return ""


def _gemini_generate_stream_with_key(
    api_key: str,
    full_prompt: str,
    temperature: float,
) -> Iterator[str]:
    """지정한 API 키로 Gemini streaming 호출."""
    import google.generativeai as genai

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    response = model.generate_content(
        full_prompt,
        generation_config={
            "temperature": temperature,
            "max_output_tokens": 4096,
        },
        stream=True,
    )

    for chunk in response:
        text = _extract_stream_chunk_text(chunk)
        if text:
            yield text


def _is_quota_error(err_str: str) -> bool:
    """429 쿼터/레이트리밋 에러 여부"""
    return "429" in err_str or "quota" in err_str.lower() or "ResourceExhausted" in err_str


def _get_retry_delay(err_str: str) -> int:
    """에러 메시지에서 retry_delay 파싱"""
    match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", err_str)
    if match:
        return int(match.group(1)) + 3
    
    delay_sec = int(os.getenv("LLM_REQUEST_DELAY_SEC", "5"))
    return delay_sec * 5


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = None,
    max_retries: int = None,
) -> str:
    """
    Gemini API 호출 (라운드로빈 키 분산 + 소진 키 캐싱)
    """
    if temperature is None:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    
    if max_retries is None:
        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
    
    global _gemini_key_index
    keys = _get_gemini_keys()
    
    if not keys:
        return "[ERROR] GEMINI_API_KEYS를 .env에 설정해주세요"
    
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    n_keys = len(keys)
    
    # 사용 가능한 키만 시도
    available_keys = [i for i in range(n_keys) if not _is_key_exhausted(i)]
    
    if not available_keys:
        print(f"  [llm] 모든 키 소진, 10초 대기 후 재시도...")
        time.sleep(10)
        # 캐시 초기화
        _exhausted_keys.clear()
        available_keys = list(range(n_keys))
    
    # 사용 가능한 키부터 시작
    start_index = _gemini_key_index
    for _ in range(len(available_keys)):
        # 다음 사용 가능한 키 찾기
        attempts = 0
        while attempts < n_keys:
            current_index = (start_index + attempts) % n_keys
            if not _is_key_exhausted(current_index):
                break
            attempts += 1
        else:
            # 모든 키 소진
            print(f"  [llm] 모든 키 소진, 10초 대기...")
            time.sleep(10)
            _exhausted_keys.clear()
            current_index = start_index
        
        api_key = keys[current_index]
        key_num = current_index + 1
        
        try:
            result = _gemini_generate_with_key(api_key, full_prompt, temperature)
            
            # 성공 시 다음 키로 이동
            _gemini_key_index = (current_index + 1) % n_keys
            
            if current_index != start_index % n_keys:
                print(f"  [llm] ✅ 키 #{key_num}로 성공")
            
            return result
        
        except Exception as e:
            err_str = str(e)
            
            if _is_quota_error(err_str):
                # 쿼터 소진 키 마크 (즉시 다음 키로)
                _mark_key_exhausted(current_index)
                start_index = current_index + 1
                time.sleep(0.2)  # 0.2초만 대기
                continue
            else:
                print(f"  [llm] Gemini 호출 실패 (키 #{key_num}): {str(e)[:100]}")
                time.sleep(2)
    
    print(f"  [llm] Gemini 최종 실패 (모든 재시도 소진)")
    return "[ERROR] LLM 호출 실패 - 재시도 초과"


def call_llm_stream(
    system_prompt: str,
    user_prompt: str,
    temperature: float = None,
    max_retries: int = None,
) -> Iterator[str]:
    """
    Gemini API streaming 호출.

    첫 토큰을 보내기 전 실패하면 기존 blocking 호출로 fallback한다. 일부 토큰이
    이미 전송된 뒤 실패하면 SSE 연결이 끊기지 않도록 짧은 오류 문구를 이어 보낸다.
    """
    if temperature is None:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    if max_retries is None:
        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))

    global _gemini_key_index
    keys = _get_gemini_keys()

    if not keys:
        yield "[ERROR] GEMINI_API_KEYS를 .env에 설정해주세요"
        return

    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    n_keys = len(keys)
    available_keys = [i for i in range(n_keys) if not _is_key_exhausted(i)]

    if not available_keys:
        print("  [llm] 모든 키 소진, 10초 대기 후 재시도...")
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
            print("  [llm] 모든 키 소진, 10초 대기...")
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
                    print(f"  [llm] ✅ 키 #{key_num} streaming 성공")
                return

            print(f"  [llm] Gemini streaming 빈 응답 (키 #{key_num})")
            break

        except Exception as e:
            err_str = str(e)

            if yielded_any:
                print(f"  [llm] Gemini streaming 중단 (키 #{key_num}): {err_str[:100]}")
                yield "\n\n[ERROR] 답변 생성 중 스트리밍이 중단되었습니다."
                return

            if _is_quota_error(err_str):
                _mark_key_exhausted(current_index)
                start_index = current_index + 1
                time.sleep(0.2)
                continue

            print(f"  [llm] Gemini streaming 실패 (키 #{key_num}): {err_str[:100]}")
            time.sleep(2)

    if yielded_any:
        return

    print("  [llm] Gemini streaming 실패, blocking 호출로 fallback")
    yield call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        max_retries=max_retries,
    )
