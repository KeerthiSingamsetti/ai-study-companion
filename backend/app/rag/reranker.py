"""
Cross-encoder reranking for the StudyMate RAG pipeline.

Uses a local sentence-transformers cross-encoder to rescore chunks
retrieved by the initial vector search, dramatically improving relevance.
"""
import logging
import os
import threading
from typing import List, Tuple

from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

# Module-level cache for the cross-encoder model
_RERANKER_MODEL = None
_MODEL_LOCK = threading.Lock()

# A stronger multilingual BGE cross-encoder than the previous MiniLM model.
# It remains local/free; set RERANKER_MODEL to override it for constrained
# environments or an experiment.
MODEL_NAME = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")


from langsmith import traceable

def _get_model() -> CrossEncoder:
    """
    Lazy-loads and returns the cross-encoder model singleton.
    Guarded by a thread lock to ensure thread safety when running under 
    FastAPI's concurrent worker pools.
    """
    global _RERANKER_MODEL
    
    # Fast path: check without acquiring lock
    if _RERANKER_MODEL is not None:
        return _RERANKER_MODEL
        
    with _MODEL_LOCK:
        # Double-check inside the lock to prevent a race condition 
        # where multiple threads pass the first check simultaneously.
        if _RERANKER_MODEL is None:
            logger.info(f"Lazy-loading reranker model: {MODEL_NAME}")
            _RERANKER_MODEL = CrossEncoder(MODEL_NAME)
            
    return _RERANKER_MODEL


@traceable(run_type="chain", name="cross_encoder_rerank")
def rerank(
    query: str, 
    chunks: List[Document], 
    top_k: int
) -> List[Tuple[Document, float]]:
    """
    Reranks a list of chunks against a query using a cross-encoder.
    
    Args:
        query: The user's original search query.
        chunks: The list of LangChain Documents retrieved by vector search.
        top_k: The maximum number of top-scoring chunks to return.
        
    Returns:
        A list of tuples containing (Document, rerank_score), sorted in 
        descending order of relevance (highest score first), truncated to top_k.
    """
    if not chunks:
        return []
        
    model = _get_model()
    
    # CrossEncoder expects a list of (query, document_text) pairs
    pairs = [[query, chunk.page_content] for chunk in chunks]
    
    # Predict returns a list of float32 scores corresponding to the pairs
    raw_scores = model.predict(pairs)
    
    # Combine chunks with their explicitly cast float scores (numpy float32 causes Pydantic issues)
    scored_chunks = [(chunk, float(score)) for chunk, score in zip(chunks, raw_scores)]
    
    # Sort descending by score
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    
    # Truncate and return
    return scored_chunks[:top_k]
