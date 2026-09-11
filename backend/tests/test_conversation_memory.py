"""Focused tests for LangGraph SQLite short-term conversation memory and history endpoints."""

from uuid import UUID
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.agent.checkpointer import close_checkpointer, create_checkpointer
from app.agent.graph import create_graph
from app.api.chat import router as chat_router
from app.api.threads import router as thread_router
from app.db.session import init_db
from app.services.chat_service import ChatService
from app.services.thread_service import ThreadService


def test_same_thread_id_restores_previous_messages() -> None:
    """A second request with one thread ID restores the first turn."""
    checkpointer = create_checkpointer(":memory:")
    graph = create_graph(
        FakeListChatModel(responses=["First response", "Second response"]),
        checkpointer=checkpointer,
    )
    service = ChatService(graph)
    thread_id = "conversation-one"

    try:
        service.chat("First question", thread_id=thread_id)
        service.chat("Second question", thread_id=thread_id)

        state = graph.get_state({"configurable": {"thread_id": thread_id}})
        assert [message.content for message in state.values["messages"]] == [
            "First question",
            "First response",
            "Second question",
            "Second response",
        ]
    finally:
        close_checkpointer(checkpointer)


def test_different_thread_ids_have_isolated_messages() -> None:
    """Distinct thread IDs restore distinct conversation histories."""
    checkpointer = create_checkpointer(":memory:")
    graph = create_graph(
        FakeListChatModel(responses=["Alpha response", "Beta response"]),
        checkpointer=checkpointer,
    )
    service = ChatService(graph)

    try:
        service.chat("Alpha question", thread_id="alpha")
        service.chat("Beta question", thread_id="beta")

        alpha_state = graph.get_state({"configurable": {"thread_id": "alpha"}})
        beta_state = graph.get_state({"configurable": {"thread_id": "beta"}})
        assert [message.content for message in alpha_state.values["messages"]] == [
            "Alpha question",
            "Alpha response",
        ]
        assert [message.content for message in beta_state.values["messages"]] == [
            "Beta question",
            "Beta response",
        ]
    finally:
        close_checkpointer(checkpointer)


def test_checkpoint_restores_conversation_after_restart() -> None:
    """A new graph restores messages saved by a previously closed saver."""
    with TemporaryDirectory(prefix="checkpoints-", dir=Path(__file__).parent) as directory:
        database_path = Path(directory) / "checkpoints.db"
        thread_id = "restart-conversation"

        first_checkpointer = create_checkpointer(database_path)
        first_service = ChatService(
            create_graph(
                FakeListChatModel(responses=["First response"]),
                checkpointer=first_checkpointer,
            )
        )
        try:
            first_service.chat("First question", thread_id=thread_id)
        finally:
            close_checkpointer(first_checkpointer)

        second_checkpointer = create_checkpointer(database_path)
        second_graph = create_graph(
            FakeListChatModel(responses=["Second response"]),
            checkpointer=second_checkpointer,
        )
        second_service = ChatService(second_graph)
        try:
            second_service.chat("Second question", thread_id=thread_id)

            state = second_graph.get_state(
                {"configurable": {"thread_id": thread_id}}
            )
            assert [message.content for message in state.values["messages"]] == [
                "First question",
                "First response",
                "Second question",
                "Second response",
            ]
        finally:
            close_checkpointer(second_checkpointer)


def test_chat_endpoint_returns_generated_thread_id() -> None:
    """The endpoint creates and returns a UUID when a request omits one."""
    app = FastAPI()
    app.state.chat_service = ChatService(
        create_graph(FakeListChatModel(responses=["Endpoint response"]))
    )
    app.include_router(chat_router)

    response = TestClient(app).post("/chat", json={"message": "Hello"})

    assert response.status_code == 200
    assert response.json()["message"] == "Endpoint response"
    UUID(response.json()["thread_id"])


def test_get_thread_messages_endpoint() -> None:
    """GET /threads/{thread_id}/messages returns chronological history from LangGraph checkpoint state."""
    init_db()
    checkpointer = create_checkpointer(":memory:")
    graph = create_graph(
        FakeListChatModel(responses=["First AI reply", "Second AI reply"]),
        checkpointer=checkpointer,
    )
    chat_service = ChatService(graph)
    thread_service = ThreadService()

    app = FastAPI()
    app.state.chat_service = chat_service
    app.state.thread_service = thread_service
    app.include_router(chat_router)
    app.include_router(thread_router)

    client = TestClient(app)

    # 1. Non-existent thread returns 404
    non_existent = client.get("/threads/non-existent-id/messages")
    assert non_existent.status_code == 404

    # 2. Send first chat message -> creates a thread and returns thread_id
    chat1 = client.post("/chat", json={"message": "Hello StudyMate"})
    assert chat1.status_code == 200
    thread_id = chat1.json()["thread_id"]

    # 3. Retrieve messages for the created thread
    res1 = client.get(f"/threads/{thread_id}/messages")
    assert res1.status_code == 200
    assert res1.json() == [
        {"role": "user", "content": "Hello StudyMate", "sources": []},
        {"role": "assistant", "content": "First AI reply", "sources": []},
    ]

    # 4. Send second message in same thread
    chat2 = client.post("/chat", json={"message": "What is Python?", "thread_id": thread_id})
    assert chat2.status_code == 200

    # 5. Verify full chronological history
    res2 = client.get(f"/threads/{thread_id}/messages")
    assert res2.status_code == 200
    assert res2.json() == [
        {"role": "user", "content": "Hello StudyMate", "sources": []},
        {"role": "assistant", "content": "First AI reply", "sources": []},
        {"role": "user", "content": "What is Python?", "sources": []},
        {"role": "assistant", "content": "Second AI reply", "sources": []},
    ]

    close_checkpointer(checkpointer)
