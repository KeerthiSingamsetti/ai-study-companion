"""Thin chatbot node factories for StudyMate's intent-routed graph.

Each factory creates a single LangGraph node that binds EXACTLY ONE tool
(or no tools for general_chat / synthesis).  Tool selection is already done
by the intent_router; these nodes are deliberately dumb — they just run the
correct model call.

Node map
--------
- ``create_general_chat_node``   → no tools, answers directly
- ``create_document_qa_node``    → binds search_uploaded_documents
- ``create_quiz_node``           → binds generate_document_quiz
- ``create_flashcard_node``      → binds generate_document_flashcards
- ``create_study_plan_node``     → binds generate_document_study_plan
- ``create_progress_node``       → binds get_study_progress
- ``create_synthesis_node``      → no tools (tool_choice="none"); picks
                                   prompt based on state["intent"]
- ``create_no_document_node``    → pure Python, returns fixed reply
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from app.agent.prompts import (
    CHATBOT_SYSTEM_PROMPT,
    FLASHCARD_RESULT_SYSTEM_PROMPT,
    GENERAL_CHAT_SYSTEM_PROMPT,
    GROUNDED_ANSWER_SYSTEM_PROMPT,
    QUIZ_RESULT_SYSTEM_PROMPT,
    STUDY_PLAN_RESULT_SYSTEM_PROMPT,
    STUDY_PROGRESS_RESULT_SYSTEM_PROMPT,
    with_memory_context,
)


from app.agent.state import AgentState

logger = logging.getLogger(__name__)

ChatbotNode = Callable[..., dict[str, list[AnyMessage]]]

_NO_DOCUMENT_REPLY = (
    "You haven't uploaded any documents to this conversation yet. "
    "Upload a PDF and then ask your question — I'll search it for you."
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared helper
# ─────────────────────────────────────────────────────────────────────────────

def _invoke_and_log(
    llm_bound: BaseChatModel,
    messages: list[AnyMessage],
    node_name: str,
) -> AIMessage:
    """Invoke *llm_bound*, log the result, and return the AIMessage."""
    response = llm_bound.invoke(messages)
    logger.info(
        "%s response: content=%r tool_calls=%s",
        node_name,
        str(response.content)[:120],
        response.tool_calls,
    )
    return response


# ─────────────────────────────────────────────────────────────────────────────
# History trimmer — keeps token usage within Groq free-tier limits
# ─────────────────────────────────────────────────────────────────────────────

_HISTORY_WINDOW = 6  # keep last N messages (≈ 3 user+assistant turns)

def _trim_history(messages: Sequence[AnyMessage]) -> list[AnyMessage]:
    """Return the most recent *_HISTORY_WINDOW* messages.

    Trimming the conversation history is the single most effective way to
    stay within Groq's free-tier 12 K TPM limit.  Earlier turns are already
    stored in the LangGraph checkpoint and can be reviewed via thread history;
    the LLM only needs recent context to give coherent replies.
    """
    return list(messages[-_HISTORY_WINDOW:])


def _messages_for_model(
    messages: Sequence[AnyMessage],
    last_message: AnyMessage | None = None,
) -> list[AnyMessage]:
    """Filter raw thread history to return conversational human and assistant messages."""
    result: list[AnyMessage] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append(msg)
        elif isinstance(msg, AIMessage):
            if not getattr(msg, "tool_calls", None):
                result.append(msg)
    return result


def _tools_for_turn(
    tools: list[BaseTool],
    last_message: AnyMessage,
) -> list[BaseTool]:
    """Determine available tools for a turn based on message type and intent."""
    if isinstance(last_message, ToolMessage):
        tool_name = getattr(last_message, "name", "")
        return [t for t in tools if t.name == tool_name]

    content = str(getattr(last_message, "content", "")).strip()
    if not content:
        return tools

    from app.agent.intent_router import Intent, classify_intent
    intent = classify_intent(content)

    if intent == Intent.GENERAL_CHAT:
        return []
    elif intent == Intent.PROGRESS:
        return [t for t in tools if t.name == "get_study_progress"]
    else:
        return [t for t in tools if t.name != "get_study_progress"]



def _safe_bind_tool(llm: BaseChatModel, tool: BaseTool | None) -> BaseChatModel:
    """Safely bind a tool to an LLM, gracefully handling None tools or test doubles."""
    if tool is None:
        return llm
    try:
        return llm.bind_tools([tool])
    except (NotImplementedError, AttributeError):
        return llm


def _safe_bind_no_tools(llm: BaseChatModel) -> BaseChatModel:
    """Safely configure an LLM with tool_choice="none" for post-tool synthesis."""
    try:
        return llm.bind_tools([], tool_choice="none")
    except (NotImplementedError, AttributeError):
        return llm


# ─────────────────────────────────────────────────────────────────────────────
# General chat — no tools
# ─────────────────────────────────────────────────────────────────────────────

def create_general_chat_node(
    llm: BaseChatModel,
    memory_context_provider: Callable[[], str] | None = None,
) -> ChatbotNode:
    """Node for GENERAL_CHAT intent: LLM only, no tools."""

    def general_chat(state: AgentState, config: RunnableConfig) -> dict[str, list[AnyMessage]]:
        messages = state.get("messages", [])
        is_new_thread = len(messages) == 1
        memory_context = (
            memory_context_provider()
            if is_new_thread and memory_context_provider
            else ""
        )
        system_prompt = with_memory_context(memory_context)
        logger.info("general_chat: answering without tools")
        response = _invoke_and_log(
            llm,
            [SystemMessage(content=system_prompt)] + _trim_history(messages),
            "general_chat",
        )
        return {"messages": [response]}

    return general_chat


# ─────────────────────────────────────────────────────────────────────────────
# Document QA — binds search_uploaded_documents only
# ─────────────────────────────────────────────────────────────────────────────

def create_document_qa_node(llm: BaseChatModel, rag_tool: BaseTool | None) -> ChatbotNode:
    """Node for DOCUMENT_QA intent: binds only the RAG tool."""

    bound = _safe_bind_tool(llm, rag_tool)

    def document_qa(state: AgentState, config: RunnableConfig) -> dict[str, list[AnyMessage]]:
        messages = state.get("messages", [])
        logger.info("document_qa: binding search_uploaded_documents")
        response = _invoke_and_log(
            bound,
            [SystemMessage(content=CHATBOT_SYSTEM_PROMPT)] + _trim_history(messages),
            "document_qa",
        )
        return {"messages": [response]}

    return document_qa


# ─────────────────────────────────────────────────────────────────────────────
# Quiz — binds generate_document_quiz only
# ─────────────────────────────────────────────────────────────────────────────

def create_quiz_node(llm: BaseChatModel, quiz_tool: BaseTool | None) -> ChatbotNode:
    """Node for QUIZ intent: binds only the quiz-generation tool."""

    bound = _safe_bind_tool(llm, quiz_tool)

    def quiz(state: AgentState, config: RunnableConfig) -> dict[str, list[AnyMessage]]:
        messages = state.get("messages", [])
        logger.info("quiz: binding generate_document_quiz")
        response = _invoke_and_log(
            bound,
            [SystemMessage(content=CHATBOT_SYSTEM_PROMPT)] + _trim_history(messages),
            "quiz",
        )
        return {"messages": [response]}

    return quiz


# ─────────────────────────────────────────────────────────────────────────────
# Flashcard — binds generate_document_flashcards only
# ─────────────────────────────────────────────────────────────────────────────

def create_flashcard_node(llm: BaseChatModel, flashcard_tool: BaseTool | None) -> ChatbotNode:
    """Node for FLASHCARD intent: binds only the flashcard tool."""

    bound = _safe_bind_tool(llm, flashcard_tool)

    def flashcard(state: AgentState, config: RunnableConfig) -> dict[str, list[AnyMessage]]:
        messages = state.get("messages", [])
        logger.info("flashcard: binding generate_document_flashcards")
        response = _invoke_and_log(
            bound,
            [SystemMessage(content=CHATBOT_SYSTEM_PROMPT)] + _trim_history(messages),
            "flashcard",
        )
        return {"messages": [response]}

    return flashcard


# ─────────────────────────────────────────────────────────────────────────────
# Study plan — binds generate_document_study_plan only
# ─────────────────────────────────────────────────────────────────────────────

def create_study_plan_node(llm: BaseChatModel, study_plan_tool: BaseTool | None) -> ChatbotNode:
    """Node for STUDY_PLAN intent: binds only the study-planner tool."""

    bound = _safe_bind_tool(llm, study_plan_tool)

    def study_plan(state: AgentState, config: RunnableConfig) -> dict[str, list[AnyMessage]]:
        messages = state.get("messages", [])
        logger.info("study_plan: binding generate_document_study_plan")
        response = _invoke_and_log(
            bound,
            [SystemMessage(content=CHATBOT_SYSTEM_PROMPT)] + _trim_history(messages),
            "study_plan",
        )
        return {"messages": [response]}

    return study_plan


# ─────────────────────────────────────────────────────────────────────────────
# Progress — binds get_study_progress only
# ─────────────────────────────────────────────────────────────────────────────

def create_progress_node(llm: BaseChatModel, progress_tool: BaseTool | None) -> ChatbotNode:
    """Node for PROGRESS intent: binds only the study-progress tool."""

    bound = _safe_bind_tool(llm, progress_tool)

    def progress(state: AgentState, config: RunnableConfig) -> dict[str, list[AnyMessage]]:
        messages = state.get("messages", [])
        logger.info("progress: binding get_study_progress")
        response = _invoke_and_log(
            bound,
            [SystemMessage(content=CHATBOT_SYSTEM_PROMPT)] + _trim_history(messages),
            "progress",
        )
        return {"messages": [response]}

    return progress


# ─────────────────────────────────────────────────────────────────────────────
# Synthesis — runs after ToolNode; no tools, picks prompt from intent
# ─────────────────────────────────────────────────────────────────────────────

_SYNTHESIS_PROMPT_MAP: dict[str, str] = {
    "quiz"        : QUIZ_RESULT_SYSTEM_PROMPT,
    "progress"    : STUDY_PROGRESS_RESULT_SYSTEM_PROMPT,
    "flashcard"   : FLASHCARD_RESULT_SYSTEM_PROMPT,
    "study_plan"  : STUDY_PLAN_RESULT_SYSTEM_PROMPT,
    "document_qa" : GROUNDED_ANSWER_SYSTEM_PROMPT,
    "general_chat": GENERAL_CHAT_SYSTEM_PROMPT,
}



def create_synthesis_node(llm: BaseChatModel) -> ChatbotNode:
    """Post-tool synthesis node: no tools bound, produces the final answer.

    Uses ``state["intent"]`` to select the correct result system prompt so
    the model knows how to present each tool's structured output.
    """
    no_tool = _safe_bind_no_tools(llm)

    def synthesis(state: AgentState, config: RunnableConfig) -> dict[str, list[AnyMessage]]:
        intent = state.get("intent", "document_qa")
        system_prompt = _SYNTHESIS_PROMPT_MAP.get(intent, GROUNDED_ANSWER_SYSTEM_PROMPT)
        messages = state.get("messages", [])
        logger.info("synthesis: intent=%s, composing final answer", intent)
        response = _invoke_and_log(
            no_tool,
            [SystemMessage(content=system_prompt)] + _trim_history(messages),
            "synthesis",
        )
        return {"messages": [response]}


    return synthesis




# ─────────────────────────────────────────────────────────────────────────────
# No-document — pure Python, no LLM call
# ─────────────────────────────────────────────────────────────────────────────

def create_no_document_node() -> ChatbotNode:
    """Node for NO_DOCUMENT intent: returns a fixed reply, no LLM call made."""

    def no_document(state: AgentState, config: RunnableConfig) -> dict[str, list[AnyMessage]]:
        logger.info("no_document: short-circuit, returning fixed reply")
        return {"messages": [AIMessage(content=_NO_DOCUMENT_REPLY)]}

    return no_document
