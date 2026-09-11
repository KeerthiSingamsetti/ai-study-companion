"""Application service for stateless StudyMate chat requests."""

from __future__ import annotations

from pathlib import Path
import logging
import re
from typing import Any

import json
from groq import BadRequestError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

from app.schemas.chat import DocumentCitation
from app.schemas.flashcard import FlashcardGenerateResponse
from app.schemas.quiz import QuizGenerateResponse
from app.schemas.planner import StudyPlanResponse
from app.schemas.thread import ThreadChatMessage
from app.services.citations import (
    extract_citation_ids,
    is_grounded_refusal,
    strip_citation_markers,
)

logger = logging.getLogger(__name__)

# Human-readable UI labels for each tool name (used in SSE events)
_TOOL_UI_LABELS: dict[str, str] = {
    "search_uploaded_documents" : "Searching documents...",
    "generate_document_quiz"    : "Generating quiz...",
    "generate_document_flashcards": "Generating flashcards...",
    "generate_document_study_plan": "Building study plan...",
    "get_study_progress"        : "Fetching your progress...",
}

# Map intent values to their expected tool name (for post-hoc event building)
_INTENT_TOOL_MAP: dict[str, str] = {
    "document_qa" : "search_uploaded_documents",
    "quiz"        : "generate_document_quiz",
    "flashcard"   : "generate_document_flashcards",
    "study_plan"  : "generate_document_study_plan",
    "progress"    : "get_study_progress",
}


def _build_sse_events(intent: str, tool_names_used: list[str]) -> list[dict[str, Any]]:
    """Build an ordered list of post-hoc SSE event dicts for a completed graph run.

    Events are emitted in logical execution order:
      llm_start → tool_start → tool_end → llm_end

    The ``tool_name`` comes from the ToolMessages actually observed in the
    graph result, so this is always accurate (no prediction required).
    """
    events: list[dict[str, Any]] = [{"event": "llm_start", "data": {"intent": intent}}]

    for tool_name in tool_names_used:
        if not tool_name:
            continue
        label = _TOOL_UI_LABELS.get(tool_name, "Processing...")
        events.append({"event": "tool_start", "data": {"tool": tool_name, "label": label}})
        events.append({"event": "tool_end",   "data": {"tool": tool_name}})

    events.append({"event": "llm_end", "data": {}})
    return events


class _FakeToolMessage:
    """Minimal ToolMessage-compatible object used in the citation extractor.

    The citation extractor only needs ``name`` and ``content``; this avoids
    importing and constructing a full LangChain ToolMessage with a tool_call_id.
    """

    artifact = None  # no structured artifact — extractor falls back to text parsing

    def __init__(self, name: str, content: str) -> None:
        self.name = name
        self.content = content


class ChatServiceError(RuntimeError):
    """Raised when the chat graph does not produce an assistant response."""


def extract_citations_from_messages(
    messages: list[Any], assistant_response: str
) -> list[DocumentCitation]:
    """Return source pages referenced by evidence markers, or all retrieved sources if markers are omitted."""
    if is_grounded_refusal(assistant_response):
        return []

    candidates: dict[int, DocumentCitation] = {}

    for message in messages:
        if isinstance(message, (ToolMessage, _FakeToolMessage)):
            tool_name = getattr(message, "name", "") or ""
            if tool_name and tool_name not in ("search_uploaded_documents", "generate_document_quiz", "generate_document_flashcards"):
                continue

            # 1. Check artifact first if set by tool
            raw_artifact = getattr(message, "artifact", None)
            if isinstance(raw_artifact, list) and raw_artifact:
                for position, item in enumerate(raw_artifact, start=1):
                    if isinstance(item, dict) and "document" in item:
                        citation_id = item.get("citation_id", position)
                        if not isinstance(citation_id, int):
                            continue
                        doc_name = Path(str(item["document"])).name
                        page_num = item.get("page")
                        page_val = int(page_num) if isinstance(page_num, int) else None
                        candidates[citation_id] = DocumentCitation(
                            document=doc_name, page=page_val
                        )
                if candidates:
                    continue

            # 2. Fallback: Parse formatted text content of ToolMessage
            content = str(message.content or "")
            if not content or "No relevant uploaded-document context" in content or "No uploaded documents" in content:
                continue

            matches = re.findall(
                r"\[(?:SOURCE:)?(\d+)\]\s+([^\n,]+)(?:,\s*page\s+(\d+))?",
                content,
            )
            for citation_id, doc_name, page_str in matches:
                doc_name = Path(doc_name.strip()).name
                page_num = int(page_str) if page_str else None
                candidates[int(citation_id)] = DocumentCitation(
                    document=doc_name, page=page_num
                )

    if not candidates:
        return []

    selected_ids = extract_citation_ids(assistant_response)
    target_ids = selected_ids if selected_ids else list(candidates.keys())

    citations: list[DocumentCitation] = []
    seen: set[tuple[str, int | None]] = set()
    for citation_id in target_ids:
        citation = candidates.get(citation_id)
        if citation is None:
            continue
        key = (citation.document, citation.page)
        if key not in seen:
            seen.add(key)
            citations.append(citation)
    return citations


class ChatService:
    """Own and invoke the compiled graph for one application process."""

    def __init__(self, graph: CompiledStateGraph, tools: list[Any] | None = None) -> None:
        """Create the service with its injected compiled graph and optional tool registry."""
        self._graph = graph
        # Keep a name → callable map so we can manually execute a tool when
        # the model generates a malformed text-based tool call.
        self._tools: dict[str, Any] = {t.name: t for t in (tools or [])}

    def _invoke(
        self,
        user_message: str,
        thread_id: str,
        *,
        reuse_pending_user_message: bool = False,
    ) -> tuple[str, list[DocumentCitation], list[Any], list[dict[str, Any]]]:
        """Invoke the graph and collect text, citations, tool payloads, and SSE events."""
        configurable: dict[str, Any] = {"thread_id": thread_id}
        result = self._graph.invoke(
            {
                "messages": []
                if reuse_pending_user_message
                else [HumanMessage(content=user_message)]
            },
            config={"configurable": configurable},
        )
        messages = result.get("messages", [])
        intent   = result.get("intent", "")

        assistant_response: str | None = None
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                assistant_response = message.text
                break

        if assistant_response is None:
            raise ChatServiceError("The chat graph completed without an assistant response.")

        tool_results: list[Any] = []
        tool_names_used: list[str] = []

        # Scope tool results and sse event discovery to the current turn's messages
        last_human_index = -1
        for index in range(len(messages) - 1, -1, -1):
            if isinstance(messages[index], HumanMessage):
                last_human_index = index
                break

        current_turn_messages = (
            messages[last_human_index:] if last_human_index != -1 else messages
        )

        for message in current_turn_messages:
            if not isinstance(message, ToolMessage):
                continue
            tool_names_used.append(message.name or "")
            if message.name == "get_study_progress":
                try:
                    raw_content = message.content
                    if isinstance(raw_content, str):
                        data = json.loads(raw_content)
                    elif isinstance(raw_content, dict):
                        data = raw_content
                    else:
                        data = {}
                    tool_results.append({
                        "type": "tool_result",
                        "tool": "progress",
                        "quiz_attempts": data.get("quiz_attempts", []),
                        "weak_topics": data.get("weak_topics", []),
                        "studied_topics": data.get("studied_topics", []),
                    })
                except Exception:
                    continue
                continue

            if message.name not in ("generate_document_quiz", "generate_document_flashcards", "generate_document_study_plan"):
                continue
            artifact = getattr(message, "artifact", None)
            if isinstance(artifact, dict) and artifact:
                tool_name = artifact.get("tool")
                if tool_name == "quiz":
                    try:
                        tool_results.append(QuizGenerateResponse.model_validate(artifact))
                    except ValueError:
                        continue
                elif tool_name == "flashcards":
                    try:
                        tool_results.append(FlashcardGenerateResponse.model_validate(artifact))
                    except ValueError:
                        continue
                elif tool_name == "study_planner":
                    try:
                        tool_results.append(StudyPlanResponse.model_validate(artifact))
                    except ValueError:
                        continue


        # Build post-hoc SSE events from intent + observed tool messages in current turn
        sse_events = _build_sse_events(intent, tool_names_used)


        citations = (
            extract_citations_from_messages(messages, assistant_response)
            if intent == "document_qa"
            else []
        )
        return strip_citation_markers(assistant_response), citations, tool_results, sse_events

    def _has_pending_user_message(self, user_message: str, thread_id: str) -> bool:
        """Return whether a failed graph attempt already checkpointed this turn."""
        try:
            state = self._graph.get_state(
                {"configurable": {"thread_id": thread_id}}
            )
        except AttributeError:
            # Lightweight test doubles need not implement LangGraph state
            # inspection; treating the turn as not checkpointed is safe there.
            return False

        messages = state.values.get("messages", []) if state and state.values else []
        if not messages or not isinstance(messages[-1], HumanMessage):
            return False
        return str(messages[-1].content) == user_message

    @staticmethod
    def _is_tool_use_failure(error: BadRequestError) -> bool:
        """Return whether Groq rejected a model-generated tool-call payload."""
        body = getattr(error, "body", None)
        if not isinstance(body, dict):
            return False
        error_details = body.get("error")
        return (
            isinstance(error_details, dict)
            and error_details.get("code") == "tool_use_failed"
        )

    @staticmethod
    def _parse_failed_generation(error: BadRequestError) -> tuple[str, dict[str, Any]] | None:
        """Extract tool name and args from Groq's failed_generation field.

        Groq returns the raw model output in ``failed_generation`` when it
        rejects a malformed tool call. llama-3.3-70b-versatile occasionally
        produces the legacy Hermes text format::

            <function=tool_name{"arg": "value"}</function>

        This method parses that string and returns ``(tool_name, args_dict)``.
        """
        body = getattr(error, "body", None)
        if not isinstance(body, dict):
            return None
        failed_gen: str = body.get("error", {}).get("failed_generation", "")
        if not failed_gen:
            return None
        # Pattern covers both <function=name{...}</function> and
        # <function=name {...}</function> (with a space before the JSON object).
        match = re.search(
            r"<function=(\w+)\s*(?:>\s*)?(\{.*?\})\s*(?:</function>|$)",
            failed_gen,
            re.DOTALL,
        )
        if not match:
            return None
        tool_name = match.group(1)
        try:
            args = json.loads(match.group(2))
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(args, dict):
            return None
        return tool_name, args

    def _invoke_with_tool_failure_retry(
        self, user_message: str, thread_id: str
    ) -> tuple[str, list[DocumentCitation], list[Any], list[dict]]:
        """Invoke the agent; on tool_use_failed, execute the tool manually.

        When llama-3.3-70b-versatile generates a legacy text-based function
        call (``<function=name{...}</function>``) Groq rejects the request
        before LangGraph can see it.  A naive graph-level retry will produce
        the same broken output again.  Instead we:

        1. Parse the intended tool name + args from ``failed_generation``.
        2. Execute the matching tool directly (bypassing the model's broken
           call).
        3. Re-invoke the LLM *without* any bound tools, passing the tool result
           as a plain HumanMessage so the model can produce the final answer.
        """
        try:
            return self._invoke(user_message, thread_id)
        except BadRequestError as error:
            if not self._is_tool_use_failure(error):
                raise

            logger.warning(
                "Groq returned tool_use_failed; attempting manual tool execution fallback.",
                exc_info=True,
            )

            parsed = self._parse_failed_generation(error)
            if parsed is not None:
                tool_name, tool_args = parsed
                tool_fn = self._tools.get(tool_name)
                if tool_fn is not None:
                    try:
                        result = self._answer_with_manual_tool_result(
                            user_message, thread_id, tool_fn, tool_args
                        )
                        if result is not None:
                            text, citations, artifacts = result
                            events = _build_sse_events("", [tool_name])
                            return text, citations, artifacts, events
                    except Exception:
                        logger.exception(
                            "Manual tool execution fallback failed for tool %r.", tool_name
                        )

            # Fallback: re-invoke the graph (or answer without tools)
            try:
                return self._invoke(
                    user_message, thread_id, reuse_pending_user_message=True
                )
            except Exception:
                try:
                    text, citations, artifacts = self._invoke_without_tools(
                        user_message, thread_id
                    )
                    return text, citations, artifacts, []
                except Exception:
                    logger.exception(
                        "No-tool fallback failed after Groq returned tool_use_failed."
                    )
                    return (
                        "I couldn't complete that tool request. Please try again.",
                        [],
                        [],
                        [],
                    )


    def _answer_with_manual_tool_result(
        self,
        user_message: str,
        thread_id: str,
        tool_fn: Any,
        tool_args: dict[str, Any],
    ) -> tuple[str, list[DocumentCitation], list[Any]] | None:
        """Execute *tool_fn* directly and feed the result back to the model.

        The tool result is injected as a system-level context block so the
        model can produce a grounded answer without needing tool-calling.
        """
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.agent.prompts import GROUNDED_ANSWER_SYSTEM_PROMPT
        from app.agent.llm import create_llm

        configurable = {"thread_id": thread_id}
        config = {"configurable": configurable}

        # Execute the tool with the thread config so it can resolve thread_id.
        tool_result = tool_fn.invoke(tool_args, config=config)
        if not tool_result or "No relevant" in str(tool_result) or "No uploaded" in str(tool_result):
            # Nothing useful retrieved; fall through to no-tool answer.
            return None

        # Build a one-shot conversation: system grounding prompt + user question
        # + tool context. No tool schema is bound, so no further tool-call
        # attempts are made.
        llm = create_llm()
        response = llm.invoke(
            [
                SystemMessage(content=GROUNDED_ANSWER_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"User question: {user_message}\n\n"
                        f"Retrieved context:\n{tool_result}"
                    )
                ),
            ]
        )
        answer = strip_citation_markers(str(response.content or ""))
        # Parse [SOURCE:N] citations from the tool result text.
        citations = extract_citations_from_messages(
            # Fake a ToolMessage list so the extractor can parse the text.
            [_FakeToolMessage(name=tool_fn.name, content=str(tool_result))],
            answer,
        )
        return answer, citations, []

    def _invoke_without_tools(
        self, user_message: str, thread_id: str
    ) -> tuple[str, list[DocumentCitation], list[Any]]:
        """Ask the LLM to answer the user's question with no tools bound at all."""
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.agent.prompts import CHATBOT_SYSTEM_PROMPT
        from app.agent.llm import create_llm

        llm = create_llm()
        response = llm.invoke(
            [
                SystemMessage(content=CHATBOT_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ]
        )
        return strip_citation_markers(str(response.content or "")), [], []

    def chat(self, user_message: str, thread_id: str) -> tuple[str, list[DocumentCitation]]:
        """Send one user message to the graph and return assistant reply and sources citations."""
        assistant_response, citations, _, _events = self._invoke_with_tool_failure_retry(
            user_message, thread_id
        )
        return assistant_response, citations

    def chat_with_tool_results(
        self, user_message: str, thread_id: str
    ) -> tuple[str, list[DocumentCitation], list[Any], list[dict]]:
        """Invoke chat; return text, citations, structured artifacts, and SSE events."""
        return self._invoke_with_tool_failure_retry(user_message, thread_id)

    def get_thread_history(self, thread_id: str) -> list[ThreadChatMessage]:
        """Retrieve and format past conversation messages from the LangGraph checkpoint state."""
        state = self._graph.get_state({"configurable": {"thread_id": thread_id}})
        messages = state.values.get("messages", []) if state and state.values else []

        history: list[ThreadChatMessage] = []
        recent_tool_messages: list[ToolMessage] = []

        for message in messages:
            if isinstance(message, ToolMessage):
                recent_tool_messages.append(message)
            elif isinstance(message, HumanMessage):
                content = str(message.content or "").strip()
                if content:
                    history.append(ThreadChatMessage(role="user", content=content))
                recent_tool_messages = []
            elif isinstance(message, AIMessage):
                content = str(message.content or "").strip()
                if content:
                    citations = (
                        extract_citations_from_messages(recent_tool_messages, content)
                        if recent_tool_messages
                        else []
                    )
                    progress_data = None
                    for tm in recent_tool_messages:
                        if tm.name == "get_study_progress":
                            try:
                                raw = tm.content
                                data = json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
                                progress_data = {
                                    "tool": "progress",
                                    "quiz_attempts": data.get("quiz_attempts", []),
                                    "weak_topics": data.get("weak_topics", []),
                                    "studied_topics": data.get("studied_topics", []),
                                }
                            except Exception:
                                pass
                    history.append(
                        ThreadChatMessage(
                            role="assistant",
                            content=strip_citation_markers(content),
                            sources=citations,
                            progress_data=progress_data,
                        )
                    )
                    recent_tool_messages = []


        return history
