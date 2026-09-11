"""Focused tests for the grounded quiz generator and structured graph result."""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool, tool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.graph import create_graph
from app.api.chat import router as chat_router
from app.db import crud
from app.db.models import Base
from app.rag.retriever import RetrievedChunk
from app.services.chat_service import ChatService
from app.tools.quiz_generator_tool import generate_quiz


class ToolCapableFakeChatModel(FakeMessagesListChatModel):
    """Fake chat model that accepts tool binding for graph tests."""

    def bind_tools(self, tools: list[BaseTool], **kwargs: object) -> "ToolCapableFakeChatModel":
        return self


def test_generate_quiz_reuses_retriever_and_logs_event(monkeypatch) -> None:
    """Quiz generation uses the document's stored index and creates a quiz log entry."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    crud.create_thread(db, thread_id="thread-1", title="Quiz thread")
    document = crud.create_document(
        db,
        document_id="document-1",
        thread_id="thread-1",
        filename="biology.pdf",
        vectorstore_path="existing-index",
    )
    retrieved: list[tuple[str, str, object]] = []

    def fake_retrieve(query: str, path: str, embeddings: object, **kwargs: object):
        retrieved.append((query, path, embeddings))
        assert kwargs["use_hybrid_search"] is True
        assert kwargs["use_reranking"] is True
        return [
            RetrievedChunk(
                content="Mitochondria produce ATP.",
                source="biology.pdf",
                page=2,
                similarity_score=0.9,
                relevance_score=0.9,
            )
        ]

    monkeypatch.setattr("app.tools.quiz_generator_tool.retrieve", fake_retrieve)
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content=(
        '{"type":"tool_result","tool":"quiz","document_id":"document-1",'
        '"topic":"ATP","difficulty":"medium","questions":['
        '{"question":"Where is ATP produced?","options":["Mitochondria","Nucleus"],'
        '"correct_index":0,"explanation":"The context names mitochondria."}]}'
    ))
    embeddings = object()

    result = generate_quiz(
        llm, document.id, "ATP", embeddings=embeddings, db=db
    )

    assert retrieved == [("ATP", "existing-index", embeddings)]
    assert result.questions[0].correct_index == 0
    assert llm.invoke.call_count == 1
    assert [entry.event_type for entry in crud.get_study_log_for_thread(db, "thread-1")] == ["quiz_generated"]


def test_streaming_chat_emits_structured_quiz_tool_result() -> None:
    """SSE clients receive quiz payloads separately from ordinary chat text."""
    quiz_payload = {
        "type": "tool_result",
        "tool": "quiz",
        "document_id": "document-1",
        "topic": "ATP",
        "difficulty": "easy",
        "questions": [],
    }

    @tool(response_format="content_and_artifact")
    def generate_document_quiz(topic: str) -> tuple[str, dict[str, object]]:
        """Generate a document quiz."""
        return "Quiz generated.", quiz_payload

    model = ToolCapableFakeChatModel(responses=[
        AIMessage(content="", tool_calls=[{
            "name": "generate_document_quiz", "args": {"topic": "ATP"}, "id": "quiz-1"
        }]),
        AIMessage(content="Your quiz is ready."),
    ])
    app = FastAPI()
    app.state.chat_service = ChatService(create_graph(model, tools=[generate_document_quiz]))
    app.include_router(chat_router)

    response = TestClient(app).post("/chat", json={"message": "Quiz me on ATP", "stream": True})

    assert response.status_code == 200
    assert "event: tool_result" in response.text
    assert '"tool":"quiz"' in response.text
    assert "event: message" in response.text
