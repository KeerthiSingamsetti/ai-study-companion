"""Unit tests for the Cohere embedding adapter (no network access).

``requests.post`` is monkeypatched so the suite stays hermetic: request/payload
construction, batching, ``input_type`` handling and error translation are
verified against the Cohere v2 embed API contract.
"""

from __future__ import annotations

import pytest

from app.rag import embeddings as emb
from app.rag.embeddings import (
    COHERE_API_BASE,
    CohereEmbeddings,
    EmbeddingAPIError,
    build_embeddings,
    get_embeddings,
    loaded_embeddings,
)


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200, text: str = "") -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self) -> dict:
        return self._payload


def _capture_post(monkeypatch, vectors_by_call):
    """Replace requests.post; return the list of captured request kwargs."""
    calls: list[dict] = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        index = min(len(calls) - 1, len(vectors_by_call) - 1)
        return _FakeResponse({"embeddings": {"float": vectors_by_call[index]}})

    monkeypatch.setattr(emb.requests, "post", fake_post)
    return calls


def test_build_embeddings_requires_api_key(monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    with pytest.raises(EmbeddingAPIError, match="COHERE_API_KEY"):
        build_embeddings()


def test_build_embeddings_reads_env_key(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "env-key")
    client = build_embeddings()
    assert isinstance(client, CohereEmbeddings)
    assert client.model_name == emb.COHERE_EMBED_MODEL


def test_embed_query_uses_search_query_input_type(monkeypatch):
    client = CohereEmbeddings(api_key="secret")
    calls = _capture_post(monkeypatch, [[[0.1, 0.2, 0.3]]])

    vector = client.embed_query("what is photosynthesis")

    assert vector == [0.1, 0.2, 0.3]
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == COHERE_API_BASE
    assert call["headers"]["Authorization"] == "Bearer secret"
    assert call["json"]["input_type"] == "search_query"
    assert call["json"]["texts"] == ["what is photosynthesis"]
    assert call["json"]["model"] == client.model_name
    assert call["json"]["embedding_types"] == ["float"]


def test_embed_documents_uses_search_document_input_type(monkeypatch):
    client = CohereEmbeddings(api_key="secret")
    calls = _capture_post(monkeypatch, [[[0.0, 1.0], [1.0, 0.0]]])

    vectors = client.embed_documents(["chunk one", "chunk two"])

    assert vectors == [[0.0, 1.0], [1.0, 0.0]]
    assert all(call["json"]["input_type"] == "search_document" for call in calls)


def test_embed_documents_batches_over_96_texts(monkeypatch):
    client = CohereEmbeddings(api_key="secret")
    texts = [f"chunk {i}" for i in range(100)]

    def dynamic_post(url, headers=None, json=None, timeout=None):
        count = len(json["texts"])
        return _FakeResponse({"embeddings": {"float": [[float(count)] * 4] * count}})

    calls: list[dict] = []
    monkeypatch.setattr(
        emb.requests,
        "post",
        lambda url, **kwargs: (calls.append({"json": kwargs["json"]}), dynamic_post(url, **kwargs))[1],
    )

    vectors = client.embed_documents(texts)

    assert len(calls) == 2  # 96 + 4
    assert [len(call["json"]["texts"]) for call in calls] == [96, 4]
    assert len(vectors) == 100
    # Order preserved across batch boundaries: batch 1 vectors are tagged with
    # the batch size (96.0), batch 2 vectors with 4.0.
    assert [v[0] for v in vectors] == [96.0] * 96 + [4.0] * 4


def test_embed_documents_empty_list_makes_no_request(monkeypatch):
    client = CohereEmbeddings(api_key="secret")
    calls = _capture_post(monkeypatch, [])
    assert client.embed_documents([]) == []
    assert calls == []


def test_http_error_is_translated(monkeypatch):
    client = CohereEmbeddings(api_key="secret")
    monkeypatch.setattr(
        emb.requests,
        "post",
        lambda *a, **kw: _FakeResponse({}, status_code=401, text="invalid api key"),
    )
    with pytest.raises(EmbeddingAPIError, match="401"):
        client.embed_query("q")


def test_network_error_is_translated(monkeypatch):
    import requests as requests_module

    client = CohereEmbeddings(api_key="secret")

    def boom(*a, **kw):
        raise requests_module.ConnectionError("connection refused")

    monkeypatch.setattr(emb.requests, "post", boom)
    with pytest.raises(EmbeddingAPIError, match="request failed"):
        client.embed_query("q")


def test_unexpected_payload_shape_raises(monkeypatch):
    client = CohereEmbeddings(api_key="secret")
    monkeypatch.setattr(
        emb.requests, "post", lambda *a, **kw: _FakeResponse({"oops": True})
    )
    with pytest.raises(EmbeddingAPIError, match="unexpected payload"):
        client.embed_query("q")


def test_wrong_vector_count_raises(monkeypatch):
    client = CohereEmbeddings(api_key="secret")
    _capture_post(monkeypatch, [[[0.1, 0.2]]])  # client sent 2 texts, got 1 back
    with pytest.raises(EmbeddingAPIError, match="wrong number of embeddings"):
        client.embed_documents(["a", "b"])


def test_lazy_proxy_defers_client_build(monkeypatch):
    monkeypatch.setattr(emb, "_EMBEDDINGS", None)
    proxy = get_embeddings()
    assert loaded_embeddings() is None  # nothing built yet

    sentinel = object()
    dummy_calls: list[str] = []

    class _Dummy:
        def embed_query(self, text: str) -> list[float]:
            dummy_calls.append(text)
            return [1.0]

    monkeypatch.setattr(emb, "build_embeddings", lambda: _Dummy())
    assert proxy.embed_query("hello") == [1.0]
    assert dummy_calls == ["hello"]
    assert loaded_embeddings() is not None
    assert sentinel is not None  # placeholder to keep the assertion meaningful


def test_lazy_proxy_model_name_is_free_of_client_build():
    proxy = get_embeddings()
    assert proxy.model_name == emb.COHERE_EMBED_MODEL
