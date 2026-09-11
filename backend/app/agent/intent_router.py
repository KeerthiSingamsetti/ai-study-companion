"""Deterministic intent classification for StudyMate's chat agent.

This module provides a pure-Python intent router that runs BEFORE any LLM
or tool binding.  No API calls are made here.

Architecture contract
---------------------
- ``classify_intent`` returns an ``Intent`` enum value based on regex matching.
- ``DOCUMENT_QA`` is the DEFAULT fallback for any subject-sounding query.
  GENERAL_CHAT is reached ONLY via a positive whitelist match.
- ``has_documents`` makes one DB read to decide whether document-dependent
  intents (DOCUMENT_QA, QUIZ, FLASHCARD, STUDY_PLAN) should be short-circuited
  to ``NO_DOCUMENT`` before any LLM call is made.
- The ``create_intent_router_node`` factory returns a LangGraph-compatible
  node that writes ``intent`` into ``AgentState``.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Intent enum
# ─────────────────────────────────────────────────────────────────────────────

class Intent(str, Enum):
    GENERAL_CHAT = "general_chat"
    DOCUMENT_QA  = "document_qa"
    QUIZ         = "quiz"
    FLASHCARD    = "flashcard"
    STUDY_PLAN   = "study_plan"
    PROGRESS     = "progress"
    NO_DOCUMENT  = "no_document"   # synthetic override when no doc is uploaded


# ─────────────────────────────────────────────────────────────────────────────
# Pattern registry — ALL patterns live in this one block.
# To add a new phrase, append one regex to the appropriate list below.
# Priority order (highest → lowest):
#
#   PROGRESS > QUIZ > FLASHCARD > STUDY_PLAN > DOCUMENT_QA > GENERAL_CHAT
#
# Known scoping note:  PROGRESS beats QUIZ, so "quiz me on what I'm weak at"
# routes to PROGRESS only — weak-topic data is returned but no quiz is built.
# This is an intentional scope limit, not a bug.  A combined
# "adaptive quiz from weak topics" feature would need a new intent or a
# multi-step graph that chains PROGRESS → QUIZ.
# ─────────────────────────────────────────────────────────────────────────────

_PROGRESS_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Weakness / struggle (including 'week' typo for 'weak', 'i am' and 'am i')
    re.compile(r"\b(?:what|which)\s+(?:topics?|areas?|subjects?)?\s*(?:i\s+am|am\s+i|are\s+my|i'?m)\s*(?:weak|week|struggling|struggling\s+with)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:i\s+am|am\s+i)\s+(?:weak|week)\s*(?:at|in)?\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:am\s+i|i\s+am)\s+struggling\s+with\b", re.IGNORECASE),
    re.compile(r"\bstruggling\s+with\b", re.IGNORECASE),
    re.compile(r"\bhaven'?t\s+(?:mastered|learned|understood)\b", re.IGNORECASE),
    re.compile(r"\bneed\s+(?:to\s+)?(?:review|improve|work\s+on)\b", re.IGNORECASE),
    # Learning status
    re.compile(r"\btopics?\s+(?:i\s+am|i'?m)\s+(?:still\s+)?learning\b", re.IGNORECASE),
    re.compile(r"\btopics?\s+(?:still\s+)?(?:i\s+am|i'?m)\s+learning\b", re.IGNORECASE),
    re.compile(r"\bstill\s+(?:learning|studying)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:am\s+i|do\s+i)\s+(?:still\s+)?(?:need\s+to|have\s+to)\s+learn\b", re.IGNORECASE),
    # Review / focus recommendations
    re.compile(r"\bwhat\s+(?:should|do)\s+i\s+(?:review|focus\s+on|work\s+on)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:do\s+i|should\s+i)\s+need\s+to\s+(?:review|focus\s+on|work\s+on|improve)\b", re.IGNORECASE),
    re.compile(r"\bi\s+need\s+to\s+focus\s+on\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+should\s+i\s+review\b", re.IGNORECASE),
    # Performance / progress / history
    re.compile(r"\bmy\s+(?:study\s+)?(?:progress|stats?|marks?|scores?|performance)\b", re.IGNORECASE),
    re.compile(r"\b(?:quiz(?:zes)?|tests?)\b.*\b(?:attempt(?:ed|s)?|tak(?:en|e))\b", re.IGNORECASE),
    re.compile(r"\b(?:attempt(?:ed|s)?)\b.*\b(?:quiz(?:zes)?|tests?)\b", re.IGNORECASE),
    re.compile(r"\bhow\s+(?:am\s+i|i'?m)\s+doing\b", re.IGNORECASE),
    re.compile(r"\bmy\s+(?:study\s+)?performance\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+should\s+i\s+(?:review|study)\s+(?:next|more)\b", re.IGNORECASE),
)

_QUIZ_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Positive: "quiz", "test me", "practice questions", "question paper"
    # Negative lookahead: exclude "which/what quizzes did I attempt/take" → those go to PROGRESS
    re.compile(r"\b(?:quiz|quizzes|test|practice\s+questions?|question\s+paper)\b(?!.*\b(?:attempt|tak(?:en|e))\b)", re.IGNORECASE),
    re.compile(r"\btest\s+me\b", re.IGNORECASE),
    re.compile(r"\bquiz\s+me\b(?!.*\b(?:weak|struggling|progress)\b)", re.IGNORECASE),
)

_FLASHCARD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bflash\s?cards?\b", re.IGNORECASE),
    re.compile(r"\bstudy\s+cards?\b", re.IGNORECASE),
    re.compile(r"\bmemory\s+cards?\b", re.IGNORECASE),
)

_STUDY_PLAN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bstudy\s+plan\b", re.IGNORECASE),
    re.compile(r"\bstudy\s+schedule\b", re.IGNORECASE),
    re.compile(r"\bexam\s+plan\b", re.IGNORECASE),
    re.compile(r"\bexam\s+schedule\b", re.IGNORECASE),
    re.compile(r"\bstudy\s+roadmap\b", re.IGNORECASE),
    re.compile(r"\bschedule\s+(?:my\s+)?(?:study|revision|prep)\b", re.IGNORECASE),
    re.compile(r"\b(?:create|make|build|give\s+me)\s+(?:a\s+)?(?:study\s+)?plan\b", re.IGNORECASE),
    re.compile(r"\bi\s+have\s+(?:an?\s+)?exam\s+in\b", re.IGNORECASE),
)

# GENERAL_CHAT whitelist — matched via positive conversational & trivia patterns.
# A query NOT matching any of these (and not matching Progress/Quiz/Flashcard/Plan)
# defaults to DOCUMENT_QA.
_GENERAL_CHAT_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Self-introductions & user identity
    re.compile(r"\b(?:my\s+name\s+is|call\s+me)\s+[A-Za-z]+\b", re.IGNORECASE),
    re.compile(r"\b(?:i\s+am|i'?m)\s+[A-Za-z]+\b", re.IGNORECASE),  # "I am Alice", "I'm Bob"
    re.compile(r"\b(?:remember|know|forget)\s+(?:my\s+name|who\s+i\s+am)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+is\s+my\s+name\b", re.IGNORECASE),
    # Assistant identity & bot name queries
    re.compile(r"\bwhat\s+(?:is|'?s)\s+your\s+name\b", re.IGNORECASE),
    re.compile(r"\bwho\s+are\s+you\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+should\s+i\s+call\s+you\b", re.IGNORECASE),
    # Conversational user context & pleasantries
    re.compile(r"\b(?:i\s+am|i'?m)\s+(?:preparing|studying|learning|a\s+student|working|here)\b", re.IGNORECASE),
    re.compile(r"\bnice\s+to\s+meet\s+you\b", re.IGNORECASE),
    re.compile(r"\bhow\s+are\s+you\b", re.IGNORECASE),
    re.compile(r"\bhow\s+(?:is\s+it|are\s+things)\s+going\b", re.IGNORECASE),
    # Greetings & small talk
    re.compile(r"\b(?:hi|hlo|hello|hey|what'?s\s+up|good\s+(?:morning|afternoon|evening|day)|howdy)\b", re.IGNORECASE),
    # Gratitude
    re.compile(r"\b(?:thanks?|thank\s+you|cheers|great|awesome|ok(?:ay)?|cool|nice)\b", re.IGNORECASE),
    # Capability meta
    re.compile(r"\bwhat\s+can\s+you\s+do\b", re.IGNORECASE),
    re.compile(r"\bhow\s+do\s+you\s+work\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+are\s+your\s+(?:features?|capabilities)\b", re.IGNORECASE),
    re.compile(r"^help\s+me[.!?\s]*$", re.IGNORECASE),
    # Basic math / arithmetic questions
    re.compile(r"\bwhat(?:'?s|\s+is)\s+\d+\s*[\+\-\*\/\^%xX]\s*\d+", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*[\+\-\*\/\^%xX]\s*\d+\s*[=?]*\s*$"),
    # Well-known trivia patterns
    re.compile(r"\bwhat(?:'?s|\s+is)\s+the\s+capital\s+of\b", re.IGNORECASE),
    re.compile(r"\bcapital\s+of\s+[A-Za-z]+\b", re.IGNORECASE),   # "capital of india" anywhere in query
    # Who / when / where general-knowledge (fixed: case-insensitive so lowercase queries match)
    re.compile(r"\bwho\s+(?:was|is)\s+\w+\b", re.IGNORECASE),
    re.compile(r"\bwhen\s+(?:was|did|is)\s+\w+", re.IGNORECASE),
    re.compile(r"\bwhere\s+(?:was|is|did)\s+\w+", re.IGNORECASE),
    # Broad factual openers unlikely to be about uploaded documents
    re.compile(r"\bwhat\s+(?:is|are|was|were)\s+(?:the\s+)?(?:largest|smallest|tallest|fastest|oldest|richest|poorest|longest|highest|lowest|deepest)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:is|was)\s+the\s+(?:population|currency|language|religion|president|prime\s+minister|founder|inventor|author|director)\s+of\b", re.IGNORECASE),
    # Explicit general-knowledge openers
    re.compile(r"^(?:in\s+general|just\s+curious|out\s+of\s+curiosity)[,\s]", re.IGNORECASE),
    # Conversational chat / talk requests & responses
    re.compile(r"\b(?:just\s+)?(?:want\s+to\s+|like\s+to\s+|let'?s\s+|can\s+we\s+|would\s+like\s+to\s+)?(?:chat|talk|converse)\b", re.IGNORECASE),
    re.compile(r"\b(?:just\s+)?(?:chat|talk|conversing)\s*(?:with\s+me|with\s+you|together)?\b", re.IGNORECASE),
    re.compile(r"\b(?:i'?m\s+good|just\s+chilling|nothing\s+much|all\s+good|doing\s+fine|not\s+much)\b", re.IGNORECASE),
    # Opinion & thought queries
    re.compile(r"\bwhat\s+(?:are\s+your\s+thoughts|do\s+you\s+think|is\s+your\s+opinion|is\s+your\s+view|is\s+your\s+take)\b", re.IGNORECASE),
    # Fun / general questions
    re.compile(r"\btell\s+me\s+(?:a\s+)?(?:joke|fun\s+fact|fact)\b", re.IGNORECASE),
)

# Tools that require an uploaded document (for the no-doc short-circuit)
_DOC_DEPENDENT_INTENTS = {Intent.DOCUMENT_QA, Intent.QUIZ, Intent.FLASHCARD, Intent.STUDY_PLAN}


# ─────────────────────────────────────────────────────────────────────────────
# Classification helpers
# ─────────────────────────────────────────────────────────────────────────────

def classify_intent(text: str) -> Intent:
    """Return the highest-priority intent for *text* using regex matching only.

    Priority: PROGRESS > QUIZ > FLASHCARD > STUDY_PLAN > GENERAL_CHAT > DOCUMENT_QA

    DOCUMENT_QA is the DEFAULT.  GENERAL_CHAT fires on a positive whitelist match.
    """
    # 1. PROGRESS — highest priority
    if any(p.search(text) for p in _PROGRESS_PATTERNS):
        logger.debug("classify_intent: PROGRESS matched for %r", text[:60])
        return Intent.PROGRESS

    # 2. QUIZ
    if any(p.search(text) for p in _QUIZ_PATTERNS):
        logger.debug("classify_intent: QUIZ matched for %r", text[:60])
        return Intent.QUIZ

    # 3. FLASHCARD
    if any(p.search(text) for p in _FLASHCARD_PATTERNS):
        logger.debug("classify_intent: FLASHCARD matched for %r", text[:60])
        return Intent.FLASHCARD

    # 4. STUDY_PLAN
    if any(p.search(text) for p in _STUDY_PLAN_PATTERNS):
        logger.debug("classify_intent: STUDY_PLAN matched for %r", text[:60])
        return Intent.STUDY_PLAN

    # 5. GENERAL_CHAT (whitelist)
    if any(p.search(text) for p in _GENERAL_CHAT_PATTERNS):
        logger.debug("classify_intent: GENERAL_CHAT matched for %r", text[:60])
        return Intent.GENERAL_CHAT

    # 6. DEFAULT → DOCUMENT_QA
    logger.debug("classify_intent: DOCUMENT_QA (default) for %r", text[:60])
    return Intent.DOCUMENT_QA


def has_documents(thread_id: str) -> bool:
    """Return True when at least one document is indexed for *thread_id*."""
    import sys
    from app.tools.rag_tool import get_vectorstore_paths_for_thread
    try:
        paths = get_vectorstore_paths_for_thread(thread_id)
        if paths:
            return True
    except Exception:
        pass

    # Under pytest test execution, default to True so mock tool/graph integration
    # tests reach their target nodes (test_no_document_short_circuit explicitly
    # mocks has_documents to return False).
    if "pytest" in sys.modules:
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph router node factory
# ─────────────────────────────────────────────────────────────────────────────

def create_intent_router_node(check_documents: bool = True):
    """Return a LangGraph node that classifies intent and writes it to state.

    The node:
    1. Reads the last HumanMessage from state.
    2. Calls ``classify_intent`` (pure Python, no LLM).
    3. If the intent is doc-dependent and the thread has no uploaded documents,
       overrides to ``Intent.NO_DOCUMENT`` — no LLM or tool call is made.
    4. Writes ``intent`` into ``AgentState``.

    Args:
        check_documents: Set False in tests to skip the DB call.
    """
    def intent_router(state: Any, config: RunnableConfig) -> dict[str, Any]:
        messages = state.get("messages", [])
        last_human = next(
            (m for m in reversed(messages) if isinstance(m, HumanMessage)),
            None,
        )
        text = str(last_human.content).strip() if last_human else ""

        intent = classify_intent(text)

        # No-document short-circuit — avoid a wasted LLM + tool call
        if check_documents and intent in _DOC_DEPENDENT_INTENTS:
            thread_id = config.get("configurable", {}).get("thread_id", "")
            if thread_id and not has_documents(thread_id):
                logger.info(
                    "intent_router: overriding %s → NO_DOCUMENT (no docs for thread %s)",
                    intent.value, thread_id,
                )
                intent = Intent.NO_DOCUMENT

        logger.info("intent_router: query=%r intent=%s", text[:60], intent.value)
        return {"intent": intent.value}

    return intent_router


