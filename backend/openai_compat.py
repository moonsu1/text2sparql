"""
OpenAI-compatible chat completions API with live KG agent streaming.
"""

import asyncio
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
    return ModelsResponse(
        object="list",
        data=[
            Model(
                id="rdf-kg-agent",
                object="model",
                created=int(time.time()),
                owned_by="rdf-kg-system",
            )
        ],
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
    use_link_prediction: Optional[bool] = None


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


STAGE_LABELS = {
    "query_analysis": "질의 분석",
    "entity_resolution": "엔티티 추출",
    "sparql_generation": "SPARQL 생성",
    "execution": "쿼리 실행",
    "link_prediction": "링크 예측",
    "answer": "최종 답변",
}

STAGE_PROGRESS_TEXT = {
    "query_analysis": "_질의를 분석하는 중입니다..._\n\n",
    "entity_resolution": "_엔티티를 확인하는 중입니다..._\n\n",
    "sparql_generation": "_SPARQL을 생성하는 중입니다..._\n\n",
    "execution": "_쿼리를 실행하는 중입니다..._\n\n",
    "link_prediction": "_누락된 관계를 예측하는 중입니다..._\n\n",
}


def _request_use_link_prediction(request: ChatCompletionRequest) -> bool:
    """OpenWebUI does not send this field, so default to enabled."""
    return True if request.use_link_prediction is None else bool(request.use_link_prediction)


async def _send_chunk(text: str, chat_id: str, model: str) -> str:
    chunk = StreamResponse(
        id=chat_id,
        created=int(time.time()),
        model=model,
        choices=[StreamChoice(index=0, delta={"content": text}, finish_reason=None)],
    )
    return f"data: {json.dumps(chunk.dict(), ensure_ascii=False)}\n\n"


async def _stream_text(text: str, chat_id: str, model: str, delay: float = 0.008):
    for char in text:
        yield await _send_chunk(char, chat_id, model)
        if delay > 0:
            await asyncio.sleep(delay)


async def _stream_chunked_text(
    text: str,
    chat_id: str,
    model: str,
    chunk_size: int = 12,
    delay: float = 0.002,
):
    for index in range(0, len(text), chunk_size):
        yield await _send_chunk(text[index:index + chunk_size], chat_id, model)
        if delay > 0:
            await asyncio.sleep(delay)


async def _stream_block(text: str, chat_id: str, model: str, delay: float = 0):
    yield await _send_chunk(text, chat_id, model)
    if delay > 0:
        await asyncio.sleep(delay)


def _stage_label(stage: Optional[str]) -> str:
    return STAGE_LABELS.get(stage or "", stage or "")


def _split_supervisor_reasoning(reasoning: str, fallback_index: int) -> tuple[int, str]:
    match = re.match(r"\*\*\[(\d+)(?:단계|.?④퀎)\]\*\*\s*(.*)", reasoning or "", re.DOTALL)
    if match:
        return int(match.group(1)), match.group(2).strip()
    return fallback_index, (reasoning or "").strip()


def _format_entities(entities: Dict[str, Any]) -> str:
    parts = [f"{key}: `{value}`" for key, value in (entities or {}).items() if value]
    return ", ".join(parts) if parts else "없음"


def _format_resolved_entities(resolved: Dict[str, Any]) -> str:
    if not resolved:
        return "확인된 엔티티 없음\n\n"

    parts = []
    person = resolved.get("person")
    if isinstance(person, dict):
        parts.append(f"person: `{person.get('label') or person.get('search_name')}`")

    place = resolved.get("place")
    if isinstance(place, list) and place:
        labels = [place.get("label", "") for place in place[:3] if place.get("label")]
        if labels:
            parts.append(f"place: `{', '.join(labels)}`")

    return ("Resolved: " + ", ".join(parts) + "\n\n") if parts else "확인된 엔티티 없음\n\n"


def _format_results_table(results: List[Dict[str, Any]], limit: int = 10) -> str:
    if not results:
        return "_결과 없음_\n\n"

    keys = list(results[0].keys())
    table = "| " + " | ".join(keys) + " |\n"
    table += "| " + " | ".join(["---"] * len(keys)) + " |\n"
    for row in results[:limit]:
        table += "| " + " | ".join(str(row.get(key, "")) for key in keys) + " |\n"
    if len(results) > limit:
        table += f"\n_... 외 {len(results) - limit}건_\n"
    return table + "\n"


def _local_id(uri: str) -> str:
    if not uri:
        return ""
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rstrip("/").rsplit("/", 1)[-1]


def _format_prediction_summary(state: Dict[str, Any]) -> str:
    predictions = state.get("predicted_triples") or []
    evidence_items = state.get("prediction_evidence") or []
    if not predictions:
        return "예측된 관계: `0`개\n\n"

    evidence_by_triple = {
        (item.get("head"), item.get("relation"), item.get("tail")): item
        for item in evidence_items
        if isinstance(item, dict)
    }

    lines = [f"예측된 관계: `{len(predictions)}`개"]
    for head, relation, tail in predictions:
        evidence = evidence_by_triple.get((head, relation, tail), {})
        relation_label = evidence.get("relation_label") or _local_id(relation)
        lines.append(f"- `{_local_id(head)}` --`log:{relation_label}`--> `{_local_id(tail)}`")
        if evidence.get("confidence") is not None:
            lines.append(f"  confidence: `{float(evidence['confidence']):.2f}`")
        lines.append(f"  evidence: {evidence.get('evidence', '근거 없음')}")

    return "\n".join(lines) + "\n\n"


def _format_supervisor_block(body: str) -> str:
    separator = "-" * 48
    body = (body or "다음 단계를 결정했습니다.").strip()
    quoted_body = "\n".join(f"> {line}" if line else ">" for line in body.splitlines())
    return f"{separator}\n###### [Supervisor]\n{quoted_body}\n{separator}\n\n"


def format_agent_event_for_markdown(event: Dict[str, Any], supervisor_index: int = 1) -> str:
    event_type = event.get("type")
    stage = event.get("stage")
    state = event.get("state") or {}

    if event_type == "answer_token":
        return event.get("delta", "")

    if event_type == "stage_start":
        if stage == "query_analysis":
            return "**질의 분석**\n" + STAGE_PROGRESS_TEXT["query_analysis"]
        if stage == "answer":
            return "## 최종 답변\n\n"
        return STAGE_PROGRESS_TEXT.get(stage, "")

    if event_type == "supervisor_decision":
        _, body = _split_supervisor_reasoning(event.get("reasoning", ""), supervisor_index)
        next_stage = event.get("next_stage")
        text = _format_supervisor_block(body)
        if next_stage and next_stage not in {"END", "answer"}:
            text += f"**{_stage_label(next_stage)}**\n"
        return text

    if event_type == "stage_complete":
        if stage == "query_analysis":
            intent = state.get("intent") or "unknown"
            target_relation = state.get("target_relation")
            time_constraint = state.get("time_constraint")
            time_text = time_constraint.get("word") if isinstance(time_constraint, dict) else "없음"
            relation_text = f"\nTarget relation: `{target_relation}`" if target_relation else ""
            return (
                f"Intent: `{intent}`{relation_text}\n"
                f"Entities: {_format_entities(state.get('entities', {}))}\n"
                f"Time: `{time_text}`\n\n"
            )

        if stage == "entity_resolution":
            return _format_resolved_entities(state.get("resolved_entities", {}))

        if stage == "sparql_generation":
            sparql = state.get("sparql_query")
            mermaid = state.get("mermaid_graph")
            result = f"```sparql\n{sparql}\n```\n\n" if sparql else "SPARQL을 생성하지 못했습니다.\n\n"
            if mermaid:
                result += f"**그래프 패턴**\n```mermaid\n{mermaid}\n```\n\n"
            return result

        if stage == "execution":
            results = state.get("sparql_results") or []
            exec_time = state.get("execution_time_ms", 0)
            return f"실행 결과: `{len(results)}`건, `{exec_time:.2f}ms`\n\n" + _format_results_table(results)

        if stage == "link_prediction":
            return _format_prediction_summary(state)

        if stage == "answer":
            if state.get("answer_streamed"):
                return ""
            answer = state.get("answer") or "답변을 생성하지 못했습니다."
            return f"## 최종 답변\n\n{answer}\n"

    if event_type == "error":
        return f"\n\n오류가 발생했습니다: `{event.get('error', '알 수 없는 오류')}`\n"

    return ""


async def stream_live_agent_response(
    request: ChatCompletionRequest,
    agent: Any,
    user_query: str,
    chat_id: str,
) -> AsyncIterator[str]:
    model = request.model

    header = StreamResponse(
        id=chat_id,
        created=int(time.time()),
        model=model,
        choices=[StreamChoice(index=0, delta={"role": "assistant"}, finish_reason=None)],
    )
    yield f"data: {json.dumps(header.dict(), ensure_ascii=False)}\n\n"

    supervisor_index = 0
    try:
        for event in agent.stream_query_events(
            query=user_query,
            use_link_prediction=_request_use_link_prediction(request),
        ):
            if event.get("type") == "supervisor_decision":
                supervisor_index += 1
            text = format_agent_event_for_markdown(event, supervisor_index)
            if text:
                async for chunk in _stream_chunked_text(text, chat_id, model):
                    yield chunk
    except Exception as e:
        async for chunk in _stream_block(f"\n\n오류가 발생했습니다: `{str(e)}`\n", chat_id, model, delay=0):
            yield chunk

    final_chunk = StreamResponse(
        id=chat_id,
        created=int(time.time()),
        model=model,
        choices=[StreamChoice(index=0, delta={}, finish_reason="stop")],
    )
    yield f"data: {json.dumps(final_chunk.dict(), ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


async def stream_response_with_progress(
    request: ChatCompletionRequest,
    result: Dict[str, Any],
    chat_id: str,
) -> AsyncIterator[str]:
    model = request.model
    header = StreamResponse(
        id=chat_id,
        created=int(time.time()),
        model=model,
        choices=[StreamChoice(index=0, delta={"role": "assistant"}, finish_reason=None)],
    )
    yield f"data: {json.dumps(header.dict(), ensure_ascii=False)}\n\n"

    async for chunk in _stream_text(_build_full_response_text(result), chat_id, model, 0.003):
        yield chunk

    final_chunk = StreamResponse(
        id=chat_id,
        created=int(time.time()),
        model=model,
        choices=[StreamChoice(index=0, delta={}, finish_reason="stop")],
    )
    yield f"data: {json.dumps(final_chunk.dict(), ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


def _build_full_response_text(result: Dict[str, Any]) -> str:
    events = result.get("execution_events") or []
    if events:
        supervisor_index = 0
        chunks = []
        for event in events:
            if event.get("type") == "supervisor_decision":
                supervisor_index += 1
            text = format_agent_event_for_markdown(event, supervisor_index)
            if text:
                chunks.append(text)
        if chunks:
            return "".join(chunks)

    parts = []
    if result.get("sparql_query"):
        parts.append(f"## SPARQL 생성\n```sparql\n{result['sparql_query']}\n```\n")
    if result.get("predicted_triples"):
        parts.append("## 링크 예측\n" + _format_prediction_summary(result))
    sparql_results = result.get("sparql_results") or []
    if sparql_results:
        parts.append(f"## 쿼리 실행\n실행 결과: `{len(sparql_results)}`건\n\n{_format_results_table(sparql_results)}")
    parts.append(f"## 최종 답변\n\n{result.get('answer', '답변을 생성하지 못했습니다.')}")
    return "\n".join(parts)


def _run_agent_full(agent: Any, user_query: str, use_link_prediction: bool) -> Dict[str, Any]:
    if not hasattr(agent, "stream_query_events"):
        return agent.query(query=user_query, use_link_prediction=use_link_prediction)

    events = []
    final_result: Dict[str, Any] = {}
    for event in agent.stream_query_events(
        query=user_query,
        use_link_prediction=use_link_prediction,
    ):
        events.append(event)
        if event.get("type") == "final":
            final_result = dict(event.get("result") or {})

    final_result.setdefault("query", user_query)
    final_result["execution_events"] = events
    return final_result


@router.post("/v1/chat/completions")
async def openai_chat_completions(request: ChatCompletionRequest):
    try:
        user_query = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                user_query = msg.content
                break

        if not user_query:
            raise HTTPException(status_code=400, detail="No user message found")

        agent = get_agent()
        chat_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"

        if request.stream:
            if hasattr(agent, "stream_query_events"):
                return StreamingResponse(
                    stream_live_agent_response(request, agent, user_query, chat_id),
                    media_type="text/event-stream",
                )

            result = _run_agent_full(
                agent,
                user_query,
                _request_use_link_prediction(request),
            )
            return StreamingResponse(
                stream_response_with_progress(request, result, chat_id),
                media_type="text/event-stream",
            )

        result = _run_agent_full(
            agent,
            user_query,
            _request_use_link_prediction(request),
        )
        full_answer = _build_full_response_text(result)

        return ChatCompletionResponse(
            id=chat_id,
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=Message(role="assistant", content=full_answer),
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                prompt_tokens=len(user_query.split()),
                completion_tokens=len(full_answer.split()),
                total_tokens=len(user_query.split()) + len(full_answer.split()),
            ),
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
