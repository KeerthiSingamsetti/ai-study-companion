"""
Custom exceptions for the StudyMate RAG pipeline.
"""
from typing import Optional

class RAGPipelineError(Exception):
    """Base class for all RAG pipeline exceptions."""
    pass


class PDFIngestError(RAGPipelineError):
    """Raised when a PDF fails to parse, is empty, or is corrupted."""
    pass


class VectorStoreLoadError(RAGPipelineError):
    """
    Raised when a vector store directory exists, but the index files 
    inside it are missing, corrupted, or otherwise unreadable.
    """
    def __init__(self, message: str, save_path: Optional[str] = None):
        super().__init__(message)
        self.save_path = save_path


class DocumentNotIndexedError(RAGPipelineError):
    """
    Raised when the retriever attempts to query a document that has 
    not been indexed (or whose index is corrupted and unreadable).
    """
    pass
