"""FastAPI endpoint for stateless StudyMate chat requests."""

import json
import logging
import time
from uuid import uuid4
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from groq import APIConnectionError, APITimeoutError, BadRequestError
from sqlalchemy.orm import Session

from app.agent.llm import resolve_model_name
from app.api.dependencies import get_chat_service, get_thread_service
from app.auth.dependencies import get_current_user
from app.db.models import User
from app.db import crud
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService, ChatServiceError
from app.services.thread_service import ThreadNotFoundError, ThreadService

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
def send_chat_message(
    payload: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    thread_service: Annotated[ThreadService, Depends(get_thread_service)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse | StreamingResponse:
    """Return the graph-generated assistant response for one user message."""
    try:
        thread = thread_service.resolve_thread(db, payload.thread_id, user_id=current_user.id)
    except ThreadNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found."
        ) from error

    call = crud.log_ai_call(
        db, model=resolve_model_name(), feature="tutor_chat", latency_ms=0,
        user_id=current_user.id, project_id=thread.id,
    )
    started = time.perf_counter()
    try:
        if payload.stream:
            assistant_message, sources, tool_results, sse_events = chat_service.chat_with_tool_results(
                payload.message, thread_id=thread.id, user_id=current_user.id, ai_call_id=call.id
            )
        else:
            assistant_message, sources = chat_service.chat(payload.message, thread_id=thread.id, user_id=current_user.id, ai_call_id=call.id)
            tool_results = []
            sse_events = []
    except ChatServiceError as error:
        crud.finish_ai_call(db, call.id, latency_ms=int((time.perf_counter() - started) * 1000), input_tokens=len(payload.message) // 4, output_tokens=0, success=False, error_msg=str(error))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The chat service did not produce a response.",
        ) from error
    except (APIConnectionError, APITimeoutError) as error:
        crud.finish_ai_call(db, call.id, latency_ms=int((time.perf_counter() - started) * 1000), input_tokens=len(payload.message) // 4, output_tokens=0, success=False, error_msg=str(error))
        logger.exception("Groq chat request failed before the agent could run a tool.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider is temporarily unavailable. Please try again.",
        ) from error
    except BadRequestError as error:
        body = getattr(error, "body", None)
        error_code = (
            body.get("error", {}).get("code") if isinstance(body, dict) else None
        )
        error_msg = str(
            body.get("error", {}).get("message", "") if isinstance(body, dict) else error
        ).lower()
        if error_code != "tool_use_failed" and "tool call validation failed" not in error_msg:
            crud.finish_ai_call(db, call.id, latency_ms=int((time.perf_counter() - started) * 1000), input_tokens=len(payload.message) // 4, output_tokens=0, success=False, error_msg=str(error))
            logger.exception("Groq rejected the chat request.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The AI provider rejected this request. Please try again.",
            ) from error

        logger.exception("Groq rejected an invalid model-generated tool call.")
        assistant_message = (
            "I couldn't complete that tool request. Please try asking again."
        )
        sources = []
        tool_results = []
        sse_events = []

    crud.finish_ai_call(db, call.id, latency_ms=int((time.perf_counter() - started) * 1000), input_tokens=len(payload.message) // 4, output_tokens=len(assistant_message) // 4, success=True)
    crud.log_event(db, event_key=f"tutor:{call.id}", user_id=current_user.id, project_id=thread.id,
                   event_type="tutor_interaction", payload_json=json.dumps({"ai_call_id": call.id, "sources": len(sources)}))
    thread_service.set_automatic_title(db, thread.id, payload.message)
    thread_service.touch_thread(db, thread.id)
    if not payload.stream:
        return ChatResponse(message=assistant_message, thread_id=thread.id, sources=sources)

    def event_stream() -> Iterator[str]:
        # Phase events (llm_start, tool_start/end, llm_end)
        for evt in sse_events:
            yield f"event: {evt['event']}\ndata: {json.dumps(evt['data'])}\n\n"
        # Structured tool payloads (quiz, flashcard, plan)
        for tool_result in tool_results:
            yield f"event: tool_result\ndata: {tool_result.model_dump_json()}\n\n"
        # Final message
        message_payload = ChatResponse(
            message=assistant_message, thread_id=thread.id, sources=sources
        )
        yield f"event: message\ndata: {json.dumps(message_payload.model_dump(mode='json'))}\n\n"
        # Explicit stream completion marker
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
