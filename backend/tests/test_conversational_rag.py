"""Integration tests for the graph's conversational RAG tool flow."""

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, tool

from app.agent.graph import create_graph


class ToolCapableFakeChatModel(FakeMessagesListChatModel):
    """Deterministic fake model that accepts tools for graph integration tests."""

    def bind_tools(self, tools: list[BaseTool], **kwargs: object) -> "ToolCapableFakeChatModel":
        """Return this fake model; supplied responses define tool decisions."""
        return self


def test_document_question_calls_tool_then_returns_grounded_answer() -> None:
    """A tool call appends context before the final assistant response."""
    calls: list[str] = []

    @tool
    def search_uploaded_documents(query: str) -> str:
        """Search uploaded documents."""
        calls.append(query)
        return "Retrieved uploaded-document context:\n\n[1] biology.pdf, page 3\nATP is produced in mitochondria."

    model = ToolCapableFakeChatModel(responses=[
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_uploaded_documents",
                    "args": {"query": "Where is ATP produced?"},
                    "id": "call-1",
                }
            ],
        ),
        AIMessage(content="According to biology.pdf (page 3), ATP is produced in mitochondria."),
    ])
    result = create_graph(model, tools=[search_uploaded_documents]).invoke(
        {"messages": [HumanMessage(content="What does my uploaded PDF say about ATP?")]}
    )

    assert calls == ["Where is ATP produced?"]
    assert result["messages"][-1].content == "According to biology.pdf (page 3), ATP is produced in mitochondria."


def test_general_conversation_does_not_call_document_tool() -> None:
    """A normal conversational response ends without a tool call."""
    calls: list[str] = []

    @tool
    def search_uploaded_documents(query: str) -> str:
        """Search uploaded documents."""
        calls.append(query)
        return "unused"

    model = ToolCapableFakeChatModel(responses=[AIMessage(content="Hello!")])
    result = create_graph(model, tools=[search_uploaded_documents]).invoke(
        {"messages": [HumanMessage(content="Hello there")]}
    )

    assert calls == []
    assert result["messages"][-1].content == "Hello!"
