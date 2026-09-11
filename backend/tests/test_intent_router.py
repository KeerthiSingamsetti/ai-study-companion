# coding: utf-8
"""Regression tests for the StudyMate intent router.

All tests are pure Python — zero Groq API calls, zero DB reads (except where
explicitly mocked).  The test suite validates:

  1. Correct Intent classification for every supported phrasing category.
  2. The PROGRESS > QUIZ > FLASHCARD > STUDY_PLAN > DOCUMENT_QA > GENERAL_CHAT
     priority ordering.
  3. The no-document short-circuit (has_documents returns False → NO_DOCUMENT).
  4. DOCUMENT_QA as the default for ambiguous subject-matter queries.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agent.intent_router import Intent, classify_intent, create_intent_router_node


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

class _FakeState:
    """Minimal AgentState-compatible dict for the router node."""
    def __init__(self, text: str) -> None:
        from langchain_core.messages import HumanMessage
        self._d = {"messages": [HumanMessage(content=text)], "intent": ""}

    def get(self, key, default=None):
        return self._d.get(key, default)


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _cls(text: str) -> Intent:
    return classify_intent(text)


# ─────────────────────────────────────────────────────────────────────────────
# GENERAL_CHAT — positive whitelist
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "Capital of France",
    "What is the capital of France?",
    "what's the capital of India",
    "hi",
    "hello",
    "hey",
    "thanks",
    "thank you",
    "Thanks a lot",
    "Thank you so much",
    "what can you do",
    "how do you work",
    "My name is John",
    "my name is santhu",
    "I am Alice",
    "I'm preparing for exams",
    "Call me Sam",
    "Remember my name",
    "What is your name",
    "Who are you",
    "Nice to meet you",
    "How are you",
    "just want to chat",
    "want to chat",
    "can we talk",
    "what are your thoughts on data centres consuming water ?",
    "what do you think about AI?",
])
def test_general_chat(query: str):
    assert _cls(query) == Intent.GENERAL_CHAT, f"Expected GENERAL_CHAT for: {query!r}"


# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENT_QA — default fallback for subject-matter questions
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "Summarize the uploaded PDF",
    "Explain inheritance",
    "explain gradient descent",
    "What is polymorphism?",
    "Tell me about neural networks from my notes",
    "what does chapter 3 say",
    "summarize my document",
])
def test_document_qa(query: str):
    assert _cls(query) == Intent.DOCUMENT_QA, f"Expected DOCUMENT_QA for: {query!r}"


# ─────────────────────────────────────────────────────────────────────────────
# QUIZ
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "Generate a quiz on chapter 3",
    "give me practice questions",
    "create a question paper",
    "test me on OOP",
])
def test_quiz(query: str):
    assert _cls(query) == Intent.QUIZ, f"Expected QUIZ for: {query!r}"


# ─────────────────────────────────────────────────────────────────────────────
# FLASHCARD
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "Make flashcards from this document",
    "create flash cards for chapter 2",
    "give me study cards on databases",
])
def test_flashcard(query: str):
    assert _cls(query) == Intent.FLASHCARD, f"Expected FLASHCARD for: {query!r}"


# ─────────────────────────────────────────────────────────────────────────────
# STUDY_PLAN
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "Create a study plan for chapter 5",
    "make me a study schedule",
    "I have an exam in 7 days",
    "build a study plan for my exam",
    "give me a study roadmap",
])
def test_study_plan(query: str):
    assert _cls(query) == Intent.STUDY_PLAN, f"Expected STUDY_PLAN for: {query!r}"


# ─────────────────────────────────────────────────────────────────────────────
# PROGRESS — original patterns
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "What quizzes did I attempt?",
    "What am I weak at?",
    "what i am week at",
    "what i am weak at",
    "what am i week at",
    "which topics am I weak at",
    "show me my progress",
    "how am I doing",
    "my performance",
    "my study stats",
])
def test_progress_original(query: str):
    assert _cls(query) == Intent.PROGRESS, f"Expected PROGRESS for: {query!r}"


# ─────────────────────────────────────────────────────────────────────────────
# PROGRESS — expanded patterns (new additions)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "can you name the topics still I am learning",
    "topics I am still learning",
    "topics I'm learning",
    "what should I review",
    "what do I need to focus on",
    "what should I work on",
    "what am I struggling with",
    "I haven't mastered pointers",
    "I haven't understood recursion",
    "I need to review sorting algorithms",
    "I need to improve on linked lists",
    "what do I still need to learn",
    "what am I still learning",
])
def test_progress_expanded(query: str):
    assert _cls(query) == Intent.PROGRESS, f"Expected PROGRESS for: {query!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Priority: PROGRESS wins over QUIZ ("quiz me on what I'm weak at")
# ─────────────────────────────────────────────────────────────────────────────

def test_progress_beats_quiz():
    """PROGRESS > QUIZ: adaptive quiz phrasing routes to PROGRESS, not QUIZ.

    Known scoping limit: no combined adaptive-quiz feature yet.
    See the priority comment in intent_router.py.
    """
    assert _cls("quiz me on what I'm weak at") == Intent.PROGRESS


# ─────────────────────────────────────────────────────────────────────────────
# NO_DOCUMENT short-circuit via has_documents() mock
# ─────────────────────────────────────────────────────────────────────────────

def test_no_document_short_circuit():
    """Router overrides DOCUMENT_QA to NO_DOCUMENT when has_documents returns False."""
    router_node = create_intent_router_node(check_documents=True)
    state = _FakeState("Explain inheritance from my notes")
    config = {"configurable": {"thread_id": "test-thread-no-docs"}}

    with patch("app.agent.intent_router.has_documents", return_value=False) as mock_hd:
        result = router_node(state, config)
        mock_hd.assert_called_once_with("test-thread-no-docs")

    assert result["intent"] == Intent.NO_DOCUMENT.value


def test_document_qa_not_overridden_when_docs_exist():
    """Router keeps DOCUMENT_QA when has_documents returns True."""
    router_node = create_intent_router_node(check_documents=True)
    state = _FakeState("Explain inheritance from my notes")
    config = {"configurable": {"thread_id": "test-thread-with-docs"}}

    with patch("app.agent.intent_router.has_documents", return_value=True):
        result = router_node(state, config)

    assert result["intent"] == Intent.DOCUMENT_QA.value


def test_progress_not_overridden_by_no_document_check():
    """PROGRESS intent is never overridden to NO_DOCUMENT (progress data is in DB, not vectorstore)."""
    router_node = create_intent_router_node(check_documents=True)
    state = _FakeState("what am I weak at")
    config = {"configurable": {"thread_id": "empty-thread"}}

    with patch("app.agent.intent_router.has_documents", return_value=False):
        result = router_node(state, config)

    # PROGRESS must survive even when there are no documents
    assert result["intent"] == Intent.PROGRESS.value


# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENT_QA as default — ensure "explain X" never hits GENERAL_CHAT
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "explain gradient descent",
    "what is recursion",
    "define polymorphism",
    "tell me about binary trees",
    "what is machine learning",
])
def test_subject_questions_are_not_general_chat(query: str):
    """Subject-matter questions must NEVER silently route to GENERAL_CHAT."""
    intent = _cls(query)
    assert intent != Intent.GENERAL_CHAT, (
        f"Subject query {query!r} incorrectly routed to GENERAL_CHAT. "
        f"Got: {intent}. Should be DOCUMENT_QA."
    )
    assert intent == Intent.DOCUMENT_QA
