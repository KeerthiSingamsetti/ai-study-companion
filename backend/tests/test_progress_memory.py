"""Tests for factual quiz-attempt storage and grounded progress data."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from groq import BadRequestError
from httpx import Request, Response
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_progress import router as progress_router
from app.api.chat import send_chat_message
from app.agent.graph import create_graph
from app.agent.nodes.chatbot import _tools_for_turn
from app.config import DEFAULT_USER_ID
from app.db import crud
from app.db.models import Base, MemoryFactType
from app.db.session import get_db
from app.schemas.chat import ChatRequest
from app.tools import memory_tool
from app.services.chat_service import ChatService
from app.services.thread_service import ThreadService


class ToolCapableFakeChatModel(FakeMessagesListChatModel):
    """Fake model that preserves LangGraph's real ToolNode execution path."""

    def bind_tools(self, tools: list[BaseTool], **kwargs: object) -> "ToolCapableFakeChatModel":
        return self


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _progress_client(session_factory: sessionmaker[Session]) -> TestClient:
    app = FastAPI()
    app.include_router(progress_router)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_quiz_result_persists_attempt_and_derives_weak_topic_below_sixty_percent() -> None:
    """A low factual score produces both an attempt row and a weak-topic fact."""
    session_factory = _session_factory()
    response = _progress_client(session_factory).post(
        "/progress/quiz-result",
        json={
            "document_id": "document-1",
            "topic": "linear regression",
            "results": [
                {"question": f"Question {index}", "correct": index < 3}
                for index in range(7)
            ],
        },
    )

    assert response.status_code == 204
    with session_factory() as db:
        attempts = crud.get_quiz_attempts(db, DEFAULT_USER_ID)
        weak_topics = crud.get_user_memory(
            db, DEFAULT_USER_ID, fact_type=MemoryFactType.WEAK_TOPIC
        )

    assert [(attempt.topic, attempt.correct_count, attempt.total_questions) for attempt in attempts] == [
        ("linear regression", 3, 7)
    ]
    assert [fact.detail for fact in weak_topics] == [
        "scored 3/7 on linear regression"
    ]


def test_passing_quiz_is_logged_without_a_weak_topic_fact() -> None:
    """A score at or above 60% never becomes a weak-topic memory."""
    session_factory = _session_factory()
    response = _progress_client(session_factory).post(
        "/progress/quiz-result",
        json={
            "document_id": "document-2",
            "topic": "probability",
            "results": [
                {"question": f"Question {index}", "correct": index < 3}
                for index in range(5)
            ],
        },
    )

    assert response.status_code == 204
    with session_factory() as db:
        attempts = crud.get_quiz_attempts(db, DEFAULT_USER_ID)
        weak_topics = crud.get_user_memory(
            db, DEFAULT_USER_ID, fact_type=MemoryFactType.WEAK_TOPIC
        )

    assert len(attempts) == 1
    assert weak_topics == []


def test_study_progress_returns_only_recorded_structured_data(monkeypatch) -> None:
    """Empty lists remain empty and a completed quiz appears without inference."""
    session_factory = _session_factory()
    with session_factory() as db:
        assert memory_tool.get_study_progress(db, DEFAULT_USER_ID) == {
            "quiz_attempts": [],
            "weak_topics": [],
            "studied_topics": [],
        }
        crud.create_quiz_attempt(
            db,
            user_id=DEFAULT_USER_ID,
            document_id="document-3",
            topic="backpropagation",
            correct_count=2,
            total_questions=5,
        )
        memory_tool.record_weak_topic(
            db,
            DEFAULT_USER_ID,
            "backpropagation",
            "scored 2/5 on backpropagation",
            "document-3",
        )

        data = memory_tool.get_study_progress(db, DEFAULT_USER_ID)

    assert data["quiz_attempts"][0]["topic"] == "backpropagation"
    assert data["quiz_attempts"][0]["score"] == "2/5"
    assert data["weak_topics"][0]["detail"] == "scored 2/5 on backpropagation"
    assert data["studied_topics"] == []

    monkeypatch.setattr(memory_tool, "SessionLocal", session_factory)
    tool = memory_tool.create_study_progress_tool()
    assert tool.args_schema.model_json_schema()["properties"] == {}
    assert tool.invoke({}) == data


def test_progress_tool_answers_from_recorded_attempts_without_retrieval(monkeypatch) -> None:
    """A performance question uses the no-input progress tool and completes."""
    session_factory = _session_factory()
    with session_factory() as db:
        crud.create_quiz_attempt(
            db,
            user_id=DEFAULT_USER_ID,
            document_id="document-4",
            topic="calculus",
            correct_count=3,
            total_questions=7,
        )
        memory_tool.record_weak_topic(
            db,
            DEFAULT_USER_ID,
            "calculus",
            "scored 3/7 on calculus",
            "document-4",
        )

    monkeypatch.setattr(memory_tool, "SessionLocal", session_factory)
    progress_tool = memory_tool.create_study_progress_tool()
    model = ToolCapableFakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_study_progress",
                        "args": {},
                        "id": "progress-1",
                    }
                ],
            ),
            AIMessage(content="Your recorded calculus quiz score is 3/7."),
        ]
    )

    response, sources = ChatService(
        create_graph(model, tools=[progress_tool])
    ).chat("Which quizzes have I attempted?", thread_id="progress-thread")

    assert response == "Your recorded calculus quiz score is 3/7."
    assert sources == []


@pytest.mark.parametrize("message", ["hi", "hlo", "thanks", "what's up"])
def test_small_talk_has_no_tools_available(message: str, monkeypatch) -> None:
    """Greetings must not be able to invoke progress or any other agent tool."""
    session_factory = _session_factory()
    monkeypatch.setattr(memory_tool, "SessionLocal", session_factory)
    progress_tool = memory_tool.create_study_progress_tool()

    @tool
    def search_uploaded_documents(query: str) -> str:
        """Search documents."""
        return query

    assert _tools_for_turn(
        [progress_tool, search_uploaded_documents], HumanMessage(content=message)
    ) == []


def test_non_progress_question_cannot_call_progress_tool(monkeypatch) -> None:
    """Only clear performance phrasing makes the progress tool available."""
    session_factory = _session_factory()
    monkeypatch.setattr(memory_tool, "SessionLocal", session_factory)
    progress_tool = memory_tool.create_study_progress_tool()

    @tool
    def search_uploaded_documents(query: str) -> str:
        """Search documents."""
        return query

    tool_names = [
        item.name
        for item in _tools_for_turn(
            [progress_tool, search_uploaded_documents],
            HumanMessage(content="Explain the concept of regression."),
        )
    ]
    assert tool_names == ["search_uploaded_documents"]


@pytest.mark.parametrize(
    "message",
    [
        "what am I weak at",
        "which topics am I weak at from your observation",
        "do you know my stats",
        "which quizzes have I attempted",
    ],
)
def test_explicit_progress_question_keeps_progress_tool_available(
    message: str, monkeypatch
) -> None:
    """Natural performance phrasings must not diverge from the prompt policy."""
    session_factory = _session_factory()
    monkeypatch.setattr(memory_tool, "SessionLocal", session_factory)
    progress_tool = memory_tool.create_study_progress_tool()

    tool_names = [
        item.name
        for item in _tools_for_turn([progress_tool], HumanMessage(content=message))
    ]
    assert tool_names == ["get_study_progress"]


def test_tool_completion_keeps_progress_schema_available(monkeypatch) -> None:
    """Groq can validate the prior tool call while the final answer is generated."""
    session_factory = _session_factory()
    monkeypatch.setattr(memory_tool, "SessionLocal", session_factory)
    progress_tool = memory_tool.create_study_progress_tool()

    tool_names = [
        item.name
        for item in _tools_for_turn(
            [progress_tool],
            ToolMessage(content="{}", name="get_study_progress", tool_call_id="call-1"),
        )
    ]
    assert tool_names == ["get_study_progress"]


def test_flashcard_learning_tag_creates_weak_topic_fact() -> None:
    """Explicit flashcard learning feedback remains a valid weak-topic signal."""
    session_factory = _session_factory()
    response = _progress_client(session_factory).post(
        "/progress/flashcard-result",
        json={
            "document_id": "document-5",
            "topic": "decision trees",
            "cards": [
                {"front": "What is entropy?", "status": "learning"},
                {"front": "What is information gain?", "status": "known"},
            ],
        },
    )

    assert response.status_code == 204
    with session_factory() as db:
        weak_topics = crud.get_user_memory(
            db, DEFAULT_USER_ID, fact_type=MemoryFactType.WEAK_TOPIC
        )
    assert [fact.detail for fact in weak_topics] == [
        "marked 1 cards as still learning on decision trees"
    ]


def test_tool_validation_failure_returns_a_graceful_chat_message() -> None:
    """A hallucinated tool call cannot surface as an unhandled API failure."""
    session_factory = _session_factory()
    error = BadRequestError(
        "tool call validation failed",
        response=Response(400, request=Request("POST", "https://api.groq.com")),
        body={"error": {"message": "tool call validation failed"}},
    )

    class FailingChatService:
        def chat(self, user_message: str, thread_id: str):
            raise error

        def chat_with_tool_results(self, user_message: str, thread_id: str):
            raise error

    with session_factory() as db:
        response = send_chat_message(
            ChatRequest(message="Which topics am I weak at?"),
            FailingChatService(),  # type: ignore[arg-type]
            ThreadService(),
            db,
        )

    assert response.message == "I couldn't complete that tool request. Please try asking again."
    assert response.sources == []
