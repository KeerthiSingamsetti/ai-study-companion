"""FastAPI endpoint for validating the existing RAG pipeline."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_rag_query_service
from app.rag.exceptions import DocumentNotIndexedError
from app.schemas.rag import RagQueryRequest, RagQueryResponse
from app.services.rag_query_service import NoRelevantChunksError, RagQueryService

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RagQueryResponse)
def query_rag(
    payload: RagQueryRequest,
    service: Annotated[RagQueryService, Depends(get_rag_query_service)],
) -> RagQueryResponse:
    """Return a grounded answer and retrieval metadata for an existing index."""
    try:
        return service.query(payload)
    except DocumentNotIndexedError as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "No index exists" in str(error)
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    except NoRelevantChunksError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
