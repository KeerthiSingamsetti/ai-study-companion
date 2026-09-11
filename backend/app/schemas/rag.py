"""HTTP contracts for the RAG debugging endpoint."""

from pydantic import BaseModel, Field

from app.schemas.chat import DocumentCitation


class RagQueryRequest(BaseModel):
    """Controls for querying one existing persisted FAISS index."""

    query: str = Field(min_length=1)
    index_path: str = Field(min_length=1)
    use_hybrid_search: bool = True
    use_reranking: bool = True
    k: int = Field(default=15, ge=1)
    rerank_top_k: int = Field(default=6, ge=1)


class RetrievedChunkResponse(BaseModel):
    """Debug representation of one retrieved source chunk."""

    content: str
    source: str
    page: int | None
    similarity_score: float
    rerank_score: float | None


class RagQueryResponse(BaseModel):
    """Grounded answer and the chunks used to produce it."""

    answer: str
    num_chunks: int
    retrieved_chunks: list[RetrievedChunkResponse]
    sources: list[DocumentCitation] = Field(default_factory=list)
