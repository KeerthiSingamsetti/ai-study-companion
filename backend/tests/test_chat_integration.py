"""Focused tests for the chat integration and citation response logic."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from groq import BadRequestError
from httpx import Request, Response
from langchain_core.language_models.fake_chat_models import FakeListChatModel, FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, tool

from app.agent.graph import create_graph
from app.api.chat import router as chat_router
from app.services.chat_service import ChatService


class ToolFailureThenRetryGraph:
    """Emulate Groq rejecting one malformed native tool-call generation."""

    def __init__(self) -> None:
        self.configurations: list[dict[str, object]] = []

    def invoke(
        self, _input: object, config: dict[str, object]
    ) -> dict[str, list[AIMessage]]:
        self.configurations.append(config)
        configurable = config["configurable"]
        assert isinstance(configurable, dict)
        if len(self.configurations) == 1:
            raise BadRequestError(
                "tool call validation failed",
                response=Response(
                    400, request=Request("POST", "https://api.groq.com")
                ),
                body={"error": {"code": "tool_use_failed"}},
            )
        return {"messages": [AIMessage(content="Plain-chat retry response")]}


class ToolCapableFakeChatModel(FakeMessagesListChatModel):
    """Fake model capable of tool binding for integration testing."""

    def bind_tools(self, tools: list[BaseTool], **kwargs: object) -> "ToolCapableFakeChatModel":
        return self


def test_graph_appends_an_assistant_message() -> None:
    """The graph accepts a user message and appends the fake LLM response."""
    graph = create_graph(FakeListChatModel(responses=["Graph response"]))

    result = graph.invoke({"messages": [HumanMessage(content="Hello")]})

    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == "Graph response"


def test_chat_service_returns_graph_assistant_response_and_sources() -> None:
    """The service converts text to a graph request and returns assistant text and sources."""
    service = ChatService(
        create_graph(FakeListChatModel(responses=["Service response"]))
    )

    message, sources = service.chat("Explain gravity", thread_id="service-test")
    assert message == "Service response"
    assert sources == []


def test_chat_service_retries_with_bound_tools_after_groq_tool_use_failure() -> None:
    """A malformed provider tool call gets one retry with tools still available."""
    graph = ToolFailureThenRetryGraph()
    service = ChatService(graph)  # type: ignore[arg-type]

    message, sources = service.chat("Explain this document", thread_id="retry-test")

    assert message == "Plain-chat retry response"
    assert sources == []
    assert graph.configurations == [
        {"configurable": {"thread_id": "retry-test"}},
        {"configurable": {"thread_id": "retry-test"}},
    ]


def test_chat_endpoint_returns_service_response() -> None:
    """The endpoint delegates to the injected application chat service."""
    app = FastAPI()
    app.state.chat_service = ChatService(
        create_graph(FakeListChatModel(responses=["Endpoint response"]))
    )
    app.include_router(chat_router)

    response = TestClient(app).post("/chat", json={"message": "What is DNA?"})

    assert response.status_code == 200
    assert response.json()["message"] == "Endpoint response"
    assert response.json()["thread_id"]
    assert response.json()["sources"] == []


def test_chat_endpoint_returns_deduplicated_sources_when_tool_used() -> None:
    """The endpoint returns deduplicated document citations when retrieval tool is used."""
    @tool
    def search_uploaded_documents(query: str) -> str:
        """Search uploaded documents in the active thread."""
        return (
            "Retrieved uploaded-document context:\n\n"
            "[1] MachineLearning.pdf, page 101\nSome text.\n\n"
            "[2] MachineLearning.pdf, page 104\nOther text.\n\n"
            "[3] MachineLearning.pdf, page 101\nDuplicate text."
        )

    model = ToolCapableFakeChatModel(responses=[
        AIMessage(
            content="",
            tool_calls=[{"name": "search_uploaded_documents", "args": {"query": "ML"}, "id": "call-1"}],
        ),
        AIMessage(content="According to MachineLearning.pdf, ML is... [[cite:1]]"),
    ])

    app = FastAPI()
    app.state.chat_service = ChatService(
        create_graph(model, tools=[search_uploaded_documents])
    )
    app.include_router(chat_router)

    response = TestClient(app).post("/chat", json={"message": "What is ML?"})

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["message"] == "According to MachineLearning.pdf, ML is..."
    assert json_data["sources"] == [{"document": "MachineLearning.pdf", "page": 101}]


def test_chat_service_suppresses_sources_for_unsupported_document_question() -> None:
    """Retrieved but irrelevant chunks must not be presented as answer sources."""
    @tool
    def search_uploaded_documents(query: str) -> str:
        """Search uploaded documents in the active thread."""
        return "[1] sample.pdf, page 339\nUnrelated document text."

    model = ToolCapableFakeChatModel(responses=[
        AIMessage(
            content="",
            tool_calls=[{"name": "search_uploaded_documents", "args": {"query": "Figure 2-4"}, "id": "call-1"}],
        ),
        AIMessage(content="I couldn't find information about Figure 2-4 in your uploaded documents."),
    ])
    service = ChatService(create_graph(model, tools=[search_uploaded_documents]))

    answer, sources = service.chat("Explain Figure 2-4", thread_id="unsupported-question")

    assert answer == "I couldn't find information about Figure 2-4 in your uploaded documents."
    assert sources == []
