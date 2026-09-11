"""Document-grounded flashcard generation backed by StudyMate's existing retriever."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain.tools import tool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import SessionLocal
from app.rag.retriever import RetrievedChunk, retrieve
from app.schemas.flashcard import FlashcardGenerateResponse
from app.config import DEFAULT_USER_ID
from app.tools.memory_tool import record_studied_topic


class FlashcardGenerationError(RuntimeError):
    """Raised when grounded flashcards cannot be generated safely."""


def _format_context(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks as bounded, traceable context evidence."""
    return "\n\n".join(
        f"[SOURCE:{index}] {Path(chunk.source).name}, page {chunk.page + 1 if chunk.page is not None else 'unknown'}\n{chunk.content}"
        for index, chunk in enumerate(chunks, start=1)
    )


def _response_content(response: Any) -> str:
    """Extract text from a LangChain chat response without provider coupling."""
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


def _validate_flashcard_json(
    payload: str,
    *,
    document_id: str,
    topic: str,
) -> FlashcardGenerateResponse:
    """Parse the model JSON and enforce request-owned metadata."""
    parsed = FlashcardGenerateResponse.model_validate_json(payload)
    if parsed.document_id != document_id or parsed.topic != topic:
        raise ValueError("The generated flashcard metadata did not match the request.")
    return parsed


def generate_flashcards(
    llm: BaseChatModel,
    document_id: str,
    topic: str,
    num_cards: int = 10,
    *,
    embeddings: Any,
    db: Session,
) -> FlashcardGenerateResponse:
    """Generate grounded recall flashcards using a single LLM attempt.

    A second LLM request is made only when the first response cannot be parsed
    as the required JSON contract.
    """
    document = crud.get_document(db, document_id)
    if document is None:
        raise FlashcardGenerationError("The requested document does not exist.")

    chunks = retrieve(
        topic,
        document.vectorstore_path,
        embeddings,
        use_hybrid_search=True,
        use_reranking=True,
        k=max(12, num_cards * 2),
        rerank_top_k=max(6, num_cards),
    )
    if not chunks:
        raise FlashcardGenerationError("No relevant document content was found for this flashcards topic.")

    context = _format_context(chunks)
    required_shape = {
        "type": "tool_result",
        "tool": "flashcards",
        "document_id": document_id,
        "topic": topic,
        "cards": [
            {
                "front": "Term or concept question",
                "back": "Concise answer or definition",
                "hint": "Optional short clue or nudge",
            }
        ],
    }
    system = SystemMessage(
        content=(
            "You create recall study flashcards using only the supplied document context. "
            "Never use outside knowledge or invent facts. Return ONLY valid JSON, with no markdown fences or prose. "
            "Every card must have a clear 'front' term/question, 'back' definition/answer, and optional 'hint'."
        )
    )
    prompt = HumanMessage(
        content=(
            f"Create exactly {num_cards} flashcards about {topic!r} from this document.\n"
            f"Required JSON shape:\n{json.dumps(required_shape)}\n\n"
            f"Document context:\n{context}"
        )
    )
    raw = _response_content(llm.invoke([system, prompt]))
    try:
        result = _validate_flashcard_json(
            raw, document_id=document_id, topic=topic
        )
    except (ValidationError, ValueError) as first_error:
        retry = HumanMessage(
            content=(
                "Your previous response was invalid. Return the corrected response as ONLY valid JSON matching this exact schema and metadata. "
                f"Schema example: {json.dumps(required_shape)}\nPrevious response:\n{raw}"
            )
        )
        try:
            result = _validate_flashcard_json(
                _response_content(llm.invoke([system, prompt, retry])),
                document_id=document_id,
                topic=topic,
            )
        except (ValidationError, ValueError) as retry_error:
            raise FlashcardGenerationError("The flashcard model did not return a valid flashcard JSON result.") from retry_error

    crud.log_study_event(
        db,
        thread_id=document.thread_id,
        document_id=document.id,
        event_type="flashcards_generated",
        topic=topic,
    )
    record_studied_topic(db, DEFAULT_USER_ID, topic, document.id)
    return result


def create_flashcard_tool(llm: BaseChatModel, embeddings: Any) -> BaseTool:
    """Create the agent tool for flashcards generation."""

    @tool(response_format="content_and_artifact")
    def generate_document_flashcards(
        topic: str,
        config: RunnableConfig,
        num_cards: int = 10,
    ) -> tuple[str, dict[str, Any]]:
        """Generate study flashcards about an uploaded document topic.

        Use this when the user asks to create flashcards, make study cards,
        or requests flashcards from their uploaded material. It uses the
        active conversation's single uploaded document. If several documents
        are uploaded, ask the user to specify one instead of guessing.
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            return "I need an active conversation before I can generate document flashcards.", {}

        db = SessionLocal()
        try:
            documents = crud.list_documents_for_thread(db, thread_id)
            if not documents:
                return "No uploaded document is available for flashcards in this conversation.", {}
            if len(documents) != 1:
                names = ", ".join(document.filename for document in documents)
                return f"Please specify which uploaded document to generate flashcards for: {names}.", {}
            result = generate_flashcards(
                llm,
                documents[0].id,
                topic,
                num_cards,
                embeddings=embeddings,
                db=db,
            )
            return "Document-grounded study flashcards have been generated.", result.model_dump(mode="json")
        except FlashcardGenerationError as error:
            return str(error), {}
        finally:
            db.close()

    return generate_document_flashcards
