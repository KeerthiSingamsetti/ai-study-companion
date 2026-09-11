"""Construction of StudyMate's intent-routed LangGraph chat workflow.

Graph topology
--------------

    START
      │
  intent_router          ← pure Python; writes state["intent"]
      │
  ┌───┴──────────────────────────────────────────────┐
  │          conditional edge: route_by_intent        │
  ▼    ▼         ▼         ▼         ▼         ▼      ▼
gen  doc_qa   quiz    flashcard study_plan progress no_doc
chat  (rag)  (quiz_t) (flash_t) (plan_t)  (prog_t)  (msg)
  │    │         │         │         │         │      │
  │    └─────────┴─────────┴─────────┴─────────┘      │
  │          tools_condition                           │
  │          ├── "tools" → ToolNode                   │
  │          │               │                        │
  │          │           synthesis                    │
  │          │               │                        │
  └──────────┴───────────────┴────────────────────────┘
                            END
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.intent_router import Intent, create_intent_router_node
from app.agent.llm import create_llm
from app.agent.nodes.chatbot import (
    create_document_qa_node,
    create_flashcard_node,
    create_general_chat_node,
    create_no_document_node,
    create_progress_node,
    create_quiz_node,
    create_study_plan_node,
    create_synthesis_node,
)
from app.agent.state import AgentState
from app.tools.memory_tool import get_default_memory_context

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Routing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _route_by_intent(state: AgentState) -> str:
    """Map state['intent'] to the corresponding graph node name."""
    intent = state.get("intent", Intent.DOCUMENT_QA.value)
    route = {
        Intent.GENERAL_CHAT.value : "general_chat",
        Intent.DOCUMENT_QA.value  : "document_qa",
        Intent.QUIZ.value         : "quiz",
        Intent.FLASHCARD.value    : "flashcard",
        Intent.STUDY_PLAN.value   : "study_plan",
        Intent.PROGRESS.value     : "progress",
        Intent.NO_DOCUMENT.value  : "no_document",
    }.get(intent, "document_qa")
    logger.info("route_by_intent: intent=%r → node=%r", intent, route)
    return route


def _route_after_chat_node(state: AgentState) -> str:
    """Log and return LangGraph's standard post-chatbot tool-routing decision."""
    decision = tools_condition(state)
    last = state["messages"][-1] if state["messages"] else None
    logger.info(
        "tools_condition=%r last_type=%s tool_calls=%s",
        decision,
        type(last).__name__ if last else None,
        last.tool_calls if isinstance(last, AIMessage) else [],
    )
    return decision


# ─────────────────────────────────────────────────────────────────────────────
# Graph factory
# ─────────────────────────────────────────────────────────────────────────────

def create_graph(
    llm: BaseChatModel | None = None,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    tools: list[BaseTool] | None = None,
) -> CompiledStateGraph:
    """Build the StudyMate intent-routed chat graph.

    Tool lookup by name from the *tools* list — callers pass the full tool
    list; the graph wires each one to its dedicated node internally.

    Args:
        llm:          Chat model; defaults to ``create_llm()``.
        checkpointer: Optional LangGraph checkpointer for persistence.
        tools:        All registered tools.  Each node pulls its own tool by
                      name so the caller need not know the graph internals.
    """
    configured_llm = llm if llm is not None else create_llm()
    tools_by_name: dict[str, BaseTool] = {t.name: t for t in (tools or [])}

    def _get(name: str) -> BaseTool | None:
        t = tools_by_name.get(name)
        if t is None:
            logger.warning("create_graph: tool %r not found — its node will error at runtime", name)
        return t

    rag_tool      = _get("search_uploaded_documents")
    quiz_tool     = _get("generate_document_quiz")
    flash_tool    = _get("generate_document_flashcards")
    plan_tool     = _get("generate_document_study_plan")
    progress_tool = _get("get_study_progress")

    # ── Build graph ──────────────────────────────────────────────────────────
    graph = StateGraph(AgentState)

    # Router (pure Python, no LLM)
    graph.add_node("intent_router", create_intent_router_node())

    # Six intent-specific chat nodes (each binds exactly one tool)
    graph.add_node("general_chat", create_general_chat_node(configured_llm, get_default_memory_context))
    graph.add_node("document_qa",  create_document_qa_node(configured_llm, rag_tool))
    graph.add_node("quiz",         create_quiz_node(configured_llm, quiz_tool))
    graph.add_node("flashcard",    create_flashcard_node(configured_llm, flash_tool))
    graph.add_node("study_plan",   create_study_plan_node(configured_llm, plan_tool))
    graph.add_node("progress",     create_progress_node(configured_llm, progress_tool))

    # Short-circuit for missing documents (pure Python, no LLM call)
    graph.add_node("no_document",  create_no_document_node())

    # Shared ToolNode for all tool-calling branches
    all_tools = [t for t in (tools or []) if t is not None]
    graph.add_node("tools",        ToolNode(all_tools))

    # Post-tool synthesis (LLM only, tool_choice="none")
    graph.add_node("synthesis",    create_synthesis_node(configured_llm))

    # ── Edges ────────────────────────────────────────────────────────────────
    graph.add_edge(START, "intent_router")

    # Intent router → one of seven branches
    graph.add_conditional_edges(
        "intent_router",
        _route_by_intent,
        {
            "general_chat": "general_chat",
            "document_qa" : "document_qa",
            "quiz"        : "quiz",
            "flashcard"   : "flashcard",
            "study_plan"  : "study_plan",
            "progress"    : "progress",
            "no_document" : "no_document",
        },
    )

    # general_chat and no_document never call tools → straight to END
    graph.add_edge("general_chat", END)
    graph.add_edge("no_document",  END)

    # Tool-capable nodes → tools_condition decides "tools" or "__end__"
    for node in ("document_qa", "quiz", "flashcard", "study_plan", "progress"):
        graph.add_conditional_edges(
            node,
            _route_after_chat_node,
            {"tools": "tools", "__end__": END},
        )

    # After ToolNode executes → synthesis produces final answer
    graph.add_edge("tools", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile(checkpointer=checkpointer)
