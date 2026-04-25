"""
Streaming Support for OpenAI-Compatible API
"""

import sys
from pathlib import Path
import time
import uuid
import json
import asyncio
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, AsyncIterator

sys.path.append(str(Path(__file__).parent.parent))

from backend.routes import get_agent

router = APIRouter()


class Model(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "rdf-kg-system"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[Model]


@router.get("/v1/models", response_model=ModelsResponse)
async def list_models():
    """List available models"""
    return ModelsResponse(
        object="list",
        data=[
            Model(
                id="rdf-kg-agent",
                object="model",
                created=int(time.time()),
                owned_by="rdf-kg-system"
            )
        ]
    )


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "rdf-kg-agent"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    stream: Optional[bool] = False


class ChatCompletionChoice(BaseModel):
    index: int
    message: Message
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage


class StreamChoice(BaseModel):
    index: int
    delta: Dict[str, str]
    finish_reason: Optional[str] = None


class StreamResponse(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[StreamChoice]


async def _send_chunk(text: str, chat_id: str, model: str) -> str:
    """텍스트 청크를 SSE 형식으로 변환"""
    chunk = StreamResponse(
        id=chat_id,
        created=int(time.time()),
        model=model,
        choices=[StreamChoice(index=0, delta={"content": text}, finish_reason=None)]
    )
    return f"data: {json.dumps(chunk.dict())}\n\n"


async def _stream_text(text: str, chat_id: str, model: str, delay: float = 0.008):
    """텍스트를 문자 단위로 스트리밍"""
    for char in text:
        yield await _send_chunk(char, chat_id, model)
        if delay > 0:
            await asyncio.sleep(delay)


async def _stream_block(text: str, chat_id: str, model: str, delay: float = 0.008):
    """텍스트 블록을 한 번에 전송 (빠른 출력용)"""
    yield await _send_chunk(text, chat_id, model)
    if delay > 0:
        await asyncio.sleep(delay)


STAGE_LABELS = {
    "query_analysis": "질의 분석",
    "entity_resolution": "엔티티 추출",
    "sparql_generation": "SPARQL 생성",
    "execution": "쿼리 실행",
    "link_prediction": "링크 예측",
    "answer": "최종 답변",
}


def _stage_label(stage: Optional[str]) -> str:
    """stage id를 사용자 표시용 이름으로 변환"""
    return STAGE_LABELS.get(stage or "", stage or "")


def _split_supervisor_reasoning(reasoning: str, fallback_index: int) -> tuple[int, str]:
    """'**[1단계]** ...' 형태의 reasoning을 단계 번호와 본문으로 분리"""
    match = re.match(r"\*\*\[(\d+)단계\]\*\*\s*(.*)", reasoning or "", re.DOTALL)
    if match:
        return int(match.group(1)), match.group(2).strip()
    return fallback_index, (reasoning or "").strip()


def _format_entities(entities: Dict[str, Any]) -> str:
    """질의 분석 entity dict를 짧게 표시"""
    if not entities:
        return "없음"

    parts = []
    for key, value in entities.items():
        if value:
            parts.append(f"{key}: `{value}`")
    return ", ".join(parts) if parts else "없음"


def _format_resolved_entities(resolved: Dict[str, Any]) -> str:
    """resolved_entities를 짧게 표시"""
    if not resolved:
        return "확인된 엔티티 없음\n\n"

    parts = []
    person = resolved.get("person")
    if isinstance(person, dict):
        parts.append(f"person: `{person.get('label') or person.get('search_name')}`")

    place = resolved.get("place")
    if isinstance(place, list) and place:
        labels = [p.get("label", "") for p in place[:3] if p.get("label")]
        if labels:
            parts.append(f"place: `{', '.join(labels)}`")

    if not parts:
        return "확인된 엔티티 없음\n\n"
    return "Resolved: " + ", ".join(parts) + "\n\n"


def _format_results_table(results: List[Dict[str, Any]], limit: int = 10) -> str:
    """SPARQL 결과를 markdown table로 변환"""
    if not results:
        return "_결과 없음_\n\n"

    keys = list(results[0].keys())
    table = "| " + " | ".join(keys) + " |\n"
    table += "| " + " | ".join(["---"] * len(keys)) + " |\n"

    for row in results[:limit]:
        table += "| " + " | ".join([str(row.get(k, "")) for k in keys]) + " |\n"

    if len(results) > limit:
        table += f"\n_... 외 {len(results) - limit}건 더_\n"

    return table + "\n"


def _format_supervisor_block(body: str) -> str:
    """Supervisor reasoning을 Markdown 보조 로그 블록으로 렌더링."""
    separator = "-" * 48
    body = (body or "다음 단계를 결정했습니다.").strip()
    quoted_body = "\n".join(f"> {line}" if line else ">" for line in body.splitlines())
    return f"{separator}\n###### [Supervisor]\n{quoted_body}\n{separator}\n\n"


def format_agent_event_for_markdown(event: Dict[str, Any], supervisor_index: int = 1) -> str:
    """
    KGAgentSupervisor의 stream_query_events 이벤트를 OpenWebUI용 markdown으로 변환.
    이 함수는 테스트 가능한 순수 formatter로 유지한다.
    """
    event_type = event.get("type")
    stage = event.get("stage")
    state = event.get("state") or {}

    if event_type == "stage_start":
        if stage == "query_analysis":
            return "**질의 분석**\n"
        # Supervisor decision chunk에서 바로 다음 stage 제목을 붙이므로 중복 출력하지 않는다.
        return ""

    if event_type == "supervisor_decision":
        step, body = _split_supervisor_reasoning(
            event.get("reasoning", ""),
            supervisor_index,
        )
        next_stage = event.get("next_stage")

        text = _format_supervisor_block(body)
        if next_stage and next_stage not in {"END", "answer"}:
            text += f"**{_stage_label(next_stage)}**\n"
        return text

    if event_type == "stage_complete":
        if stage == "query_analysis":
            intent = state.get("intent") or "unknown"
            entities = _format_entities(state.get("entities", {}))
            time_constraint = state.get("time_constraint")
            time_text = time_constraint.get("word") if isinstance(time_constraint, dict) else "없음"
            return f"Intent: `{intent}`\nEntities: {entities}\nTime: `{time_text}`\n\n"

        if stage == "entity_resolution":
            return _format_resolved_entities(state.get("resolved_entities", {}))

        if stage == "sparql_generation":
            sparql = state.get("sparql_query")
            if not sparql:
                return "SPARQL을 생성하지 못했습니다.\n\n"
            return f"```sparql\n{sparql}\n```\n\n"

        if stage == "execution":
            results = state.get("sparql_results") or []
            exec_time = state.get("execution_time_ms", 0)
            return (
                f"실행 결과: `{len(results)}`건, `{exec_time:.2f}ms`\n\n"
                + _format_results_table(results)
            )

        if stage == "link_prediction":
            predictions = state.get("predicted_triples") or []
            return f"예측된 관계: `{len(predictions)}`개\n\n"

        if stage == "answer":
            answer = state.get("answer") or "답변을 생성할 수 없습니다."
            return f"## 최종 답변\n\n{answer}\n"

    if event_type == "error":
        error = event.get("error", "알 수 없는 오류")
        return f"\n\n오류가 발생했습니다: `{error}`\n"

    return ""


async def stream_live_agent_response(
    request: ChatCompletionRequest,
    agent: Any,
    user_query: str,
    chat_id: str,
) -> AsyncIterator[str]:
    """KGAgentSupervisor 이벤트를 실제 OpenAI SSE chunk로 변환"""
    model = request.model

    header = StreamResponse(
        id=chat_id,
        created=int(time.time()),
        model=model,
        choices=[StreamChoice(index=0, delta={"role": "assistant"}, finish_reason=None)]
    )
    yield f"data: {json.dumps(header.dict())}\n\n"

    supervisor_index = 0

    try:
        for event in agent.stream_query_events(
            query=user_query,
            use_link_prediction=False,
        ):
            if event.get("type") == "supervisor_decision":
                supervisor_index += 1

            text = format_agent_event_for_markdown(event, supervisor_index)
            if not text:
                continue

            async for chunk in _stream_block(text, chat_id, model, delay=0):
                yield chunk
    except Exception as e:
        async for chunk in _stream_block(
            f"\n\n오류가 발생했습니다: `{str(e)}`\n",
            chat_id,
            model,
            delay=0,
        ):
            yield chunk

    final_chunk = StreamResponse(
        id=chat_id,
        created=int(time.time()),
        model=model,
        choices=[StreamChoice(index=0, delta={}, finish_reason="stop")]
    )
    yield f"data: {json.dumps(final_chunk.dict())}\n\n"
    yield "data: [DONE]\n\n"


async def stream_response_with_progress(
    request: ChatCompletionRequest,
    result: Dict[str, Any],
    chat_id: str
) -> AsyncIterator[str]:
    """
    Supervisor reasoning + workflow + SPARQL + results + answer를 순서대로 스트리밍
    
    출력 순서:
      1. 🧠 Supervisor 판단 (각 reasoning 순서대로)
      2. 🔄 진행 단계 (workflow path)
      3. 📝 생성된 SPARQL 쿼리
      4. 📊 실행 결과 (테이블)
      5. 💬 최종 답변
    """
    model = request.model
    
    # ── 헤더 청크 (role) ─────────────────────────────────
    header = StreamResponse(
        id=chat_id,
        created=int(time.time()),
        model=model,
        choices=[StreamChoice(index=0, delta={"role": "assistant"}, finish_reason=None)]
    )
    yield f"data: {json.dumps(header.dict())}\n\n"
    
    # ── 1. Supervisor Reasoning ───────────────────────────
    reasoning_log = result.get("supervisor_reasoning_log", [])
    if reasoning_log:
        async for chunk in _stream_text("## 🧠 Supervisor 판단\n\n", chat_id, model, 0.005):
            yield chunk
        
        for reasoning in reasoning_log:
            # 💭 reasoning 한 줄씩 출력
            line = f"💭 {reasoning}\n\n"
            async for chunk in _stream_text(line, chat_id, model, 0.006):
                yield chunk
    
    # ── 2. Workflow Path ──────────────────────────────────
    if result.get("workflow_path"):
        # 핵심 stage만 표시 (supervisor 반복 제거)
        path = result["workflow_path"]
        key_stages = [s for s in path if s != "supervisor"]
        
        path_text = f"**진행 단계:** {' → '.join(key_stages)}\n\n"
        async for chunk in _stream_text(path_text, chat_id, model, 0.005):
            yield chunk
    
    # ── 3. SPARQL 쿼리 ───────────────────────────────────
    if result.get("sparql_query"):
        sparql = result["sparql_query"]
        
        async for chunk in _stream_text("## 📝 생성된 SPARQL 쿼리\n\n```sparql\n", chat_id, model, 0.004):
            yield chunk
        
        # SPARQL은 빠르게 출력
        async for chunk in _stream_text(sparql, chat_id, model, 0.002):
            yield chunk
        
        async for chunk in _stream_text("\n```\n\n", chat_id, model, 0.004):
            yield chunk
    
    # ── 4. 실행 결과 ──────────────────────────────────────
    sparql_results = result.get("sparql_results") or []
    if sparql_results:
        header_text = f"## 📊 실행 결과 ({len(sparql_results)}건)\n\n"
        async for chunk in _stream_text(header_text, chat_id, model, 0.005):
            yield chunk
        
        # 테이블 헤더
        keys = list(sparql_results[0].keys())
        table_header = "| " + " | ".join(keys) + " |\n"
        table_header += "| " + " | ".join(["---"] * len(keys)) + " |\n"
        async for chunk in _stream_text(table_header, chat_id, model, 0.004):
            yield chunk
        
        # 데이터 (최대 10건)
        for row in sparql_results[:10]:
            row_text = "| " + " | ".join([str(row.get(k, "")) for k in keys]) + " |\n"
            async for chunk in _stream_text(row_text, chat_id, model, 0.003):
                yield chunk
        
        if len(sparql_results) > 10:
            async for chunk in _stream_text(
                f"\n_... 외 {len(sparql_results) - 10}건 더_\n\n",
                chat_id, model, 0.004
            ):
                yield chunk
        
        exec_time = result.get("execution_time_ms", 0)
        async for chunk in _stream_text(
            f"\n⏱️ **실행 시간:** {exec_time:.2f}ms\n\n",
            chat_id, model, 0.005
        ):
            yield chunk
    
    elif result.get("sparql_query"):
        # SPARQL은 있지만 결과가 없는 경우
        async for chunk in _stream_text(
            "## 📊 실행 결과\n\n_결과 없음 (데이터가 충분하지 않습니다)_\n\n",
            chat_id, model, 0.005
        ):
            yield chunk
    
    # ── 5. 최종 답변 ─────────────────────────────────────
    async for chunk in _stream_text("## 최종 답변\n\n", chat_id, model, 0.005):
        yield chunk
    
    answer = result.get("answer") or "답변을 생성할 수 없습니다."
    async for chunk in _stream_text(answer, chat_id, model, 0.01):
        yield chunk
    
    # ── 종료 청크 ─────────────────────────────────────────
    final_chunk = StreamResponse(
        id=chat_id,
        created=int(time.time()),
        model=model,
        choices=[StreamChoice(index=0, delta={}, finish_reason="stop")]
    )
    yield f"data: {json.dumps(final_chunk.dict())}\n\n"
    yield "data: [DONE]\n\n"


def _build_full_response_text(result: Dict[str, Any]) -> str:
    """Non-streaming용 전체 응답 텍스트 조합"""
    parts = []
    
    # Supervisor Reasoning
    reasoning_log = result.get("supervisor_reasoning_log", [])
    if reasoning_log:
        parts.append("## 🧠 Supervisor 판단\n")
        for r in reasoning_log:
            parts.append(f"💭 {r}")
        parts.append("")
    
    # Workflow Path
    if result.get("workflow_path"):
        path = result["workflow_path"]
        key_stages = [s for s in path if s != "supervisor"]
        parts.append(f"**진행 단계:** {' → '.join(key_stages)}\n")
    
    # SPARQL
    if result.get("sparql_query"):
        parts.append(f"## 📝 생성된 SPARQL 쿼리\n```sparql\n{result['sparql_query']}\n```\n")
    
    # Results
    sparql_results = result.get("sparql_results") or []
    if sparql_results:
        parts.append(f"## 📊 실행 결과 ({len(sparql_results)}건)\n")
        keys = list(sparql_results[0].keys())
        table = "| " + " | ".join(keys) + " |\n"
        table += "| " + " | ".join(["---"] * len(keys)) + " |\n"
        for row in sparql_results[:10]:
            table += "| " + " | ".join([str(row.get(k, "")) for k in keys]) + " |\n"
        parts.append(table)
        parts.append(f"⏱️ **실행 시간:** {result.get('execution_time_ms', 0):.2f}ms\n")
    
    # Answer
    parts.append(f"## 최종 답변\n\n{result.get('answer', '답변을 생성할 수 없습니다.')}")
    
    return "\n".join(parts)


@router.post("/v1/chat/completions")
async def openai_chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint
    Streaming 지원
    """
    try:
        # 사용자 메시지 추출
        user_query = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                user_query = msg.content
                break
        
        if not user_query:
            raise HTTPException(status_code=400, detail="No user message found")
        
        agent = get_agent()
        chat_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        
        # Streaming: Supervisor agent는 실제 실행 이벤트를 즉시 SSE로 전달
        if request.stream:
            if hasattr(agent, "stream_query_events"):
                return StreamingResponse(
                    stream_live_agent_response(request, agent, user_query, chat_id),
                    media_type="text/event-stream"
                )

            # Fallback: 고정 workflow agent는 기존 방식 유지
            result = agent.query(query=user_query, use_link_prediction=False)
            return StreamingResponse(
                stream_response_with_progress(request, result, chat_id),
                media_type="text/event-stream"
            )
        
        # Non-streaming
        result = agent.query(query=user_query, use_link_prediction=False)
        full_answer = _build_full_response_text(result)
        
        return ChatCompletionResponse(
            id=chat_id,
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=Message(role="assistant", content=full_answer),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=len(user_query.split()),
                completion_tokens=len(full_answer.split()),
                total_tokens=len(user_query.split()) + len(full_answer.split())
            )
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
