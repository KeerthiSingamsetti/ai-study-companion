"""Regression tests for tool routing after a completed tool conversation."""

from collections.abc import Callable

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from pydantic import PrivateAttr

from app.agent.checkpointer import close_checkpointer, create_checkpointer
from app.agent.graph import create_graph
from app.agent.nodes.chatbot import _messages_for_model
from app.services.chat_service import ChatService


class RecordingToolChatModel(FakeMessagesListChatModel):
    """Fake model that records exactly which tools were available each turn."""

    _bound_tool_names: list[list[str]] = PrivateAttr(default_factory=list)

    def bind_tools(
        self, tools: list[BaseTool], **kwargs: object
    ) -> "RecordingToolChatModel":
        self._bound_tool_names.append([tool.name for tool in tools])
        return self

    @property
    def bound_tool_names(self) -> list[list[str]]:
        """Expose recorded per-turn bind lists for assertions."""
        return self._bound_tool_names


def _tool_call(name: str, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": {"topic": "linear regression"}, "id": call_id}])


def _service_for_sequence(
    follow_up_response: list[AIMessage],
) -> tuple[ChatService, RecordingToolChatModel, list[str], list[str], Callable[[], None]]:
    quiz_calls: list[str] = []
    rag_calls: list[str] = []

    @tool
    def generate_document_quiz(topic: str) -> str:
        """Generate a quiz from the current study material."""
        quiz_calls.append(topic)
        return "Quiz generated."

    @tool
    def search_uploaded_documents(topic: str) -> str:
        """Search uploaded documents."""
        rag_calls.append(topic)
        return "Retrieved document context."

    model = RecordingToolChatModel(
        responses=[
            _tool_call("generate_document_quiz", "quiz-1"),
            AIMessage(content="Your quiz is ready."),
            *follow_up_response,
        ]
    )
    checkpointer = create_checkpointer(":memory:")
    service = ChatService(
        create_graph(
            model,
            checkpointer=checkpointer,
            tools=[generate_document_quiz, search_uploaded_documents],
        )
    )
    return service, model, quiz_calls, rag_calls, lambda: close_checkpointer(checkpointer)


@pytest.mark.parametrize("message", ["hello", "thanks"])
def test_completed_quiz_then_small_talk_does_not_bind_or_invoke_tools(message: str) -> None:
    """A greeting after a quiz is a direct base-LLM response, not a new tool turn."""
    service, model, quiz_calls, rag_calls, close = _service_for_sequence(
        [AIMessage(content="Hello! How can I help?")]
    )
    try:
        service.chat("Generate a quiz", thread_id="quiz-then-small-talk")
        bindings_after_quiz = len(model.bound_tool_names)
        answer, _ = service.chat(message, thread_id="quiz-then-small-talk")

        assert answer == "Hello! How can I help?"
        assert quiz_calls == ["linear regression"]
        assert rag_calls == []
        assert len(model.bound_tool_names) == bindings_after_quiz
    finally:
        close()


def test_completed_quiz_then_document_question_invokes_rag_only() -> None:
    """A later explanation request selects RAG based on its current message."""
    service, _, quiz_calls, rag_calls, close = _service_for_sequence(
        [
            _tool_call("search_uploaded_documents", "rag-1"),
            AIMessage(content="Linear regression models a continuous target."),
        ]
    )
    try:
        service.chat("Generate a quiz", thread_id="quiz-then-rag")
        answer, _ = service.chat("Explain linear regression", thread_id="quiz-then-rag")

        assert answer == "Linear regression models a continuous target."
        assert quiz_calls == ["linear regression"]
        assert rag_calls == ["linear regression"]
    finally:
        close()


def test_completed_quiz_then_quiz_request_invokes_quiz_again() -> None:
    """A new explicit quiz request, unlike small talk, can invoke the quiz tool."""
    service, _, quiz_calls, rag_calls, close = _service_for_sequence(
        [
            _tool_call("generate_document_quiz", "quiz-2"),
            AIMessage(content="Your next quiz is ready."),
        ]
    )
    try:
        service.chat("Generate a quiz", thread_id="quiz-then-quiz")
        answer, _ = service.chat("Generate another quiz", thread_id="quiz-then-quiz")

        assert answer == "Your next quiz is ready."
        assert quiz_calls == ["linear regression", "linear regression"]
        assert rag_calls == []
    finally:
        close()


def test_new_turn_model_history_excludes_completed_tool_protocol() -> None:
    """Only conversational user/assistant text survives into a later turn."""
    messages = [
        HumanMessage(content="Generate a quiz"),
        _tool_call("generate_document_quiz", "quiz-3"),
        ToolMessage(content="Quiz generated.", name="generate_document_quiz", tool_call_id="quiz-3"),
        AIMessage(content="Your quiz is ready."),
        HumanMessage(content="hello"),
    ]

    model_messages = _messages_for_model(messages, messages[-1])

    assert [message.content for message in model_messages] == [
        "Generate a quiz",
        "Your quiz is ready.",
        "hello",
    ]
