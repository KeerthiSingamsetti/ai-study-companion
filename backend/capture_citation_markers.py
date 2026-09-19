"""One-off diagnostic: capture the RAW synthesis output from the production chat graph.

Runs the REAL compiled graph (intent router, rag_tool ToolMessage, synthesis
node, real Groq model) exactly as app.main wires it. Only the embedding
provider is faked — a deterministic offline LangChain ``Embeddings`` subclass —
and the database/checkpoints live in a scratch SQLite file, so nothing touches
the dev database. Prints repr() of the raw pre-strip model output and of the
post-service message, so any citation-marker mismatch or strip gap is visible.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR / ".env", override=False)

# Scratch DB + reranking off BEFORE any app.* import reads the environment.
_SCRATCH = Path(tempfile.mkdtemp(prefix="cite_diag_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_SCRATCH / 'diag.db'}"
os.environ.setdefault("RERANKING_ENABLED", "false")

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.agent.checkpointer import close_checkpointer, create_checkpointer
from app.agent.graph import create_graph
from app.agent.llm import create_llm, create_quiz_llm
from app.db import crud
from app.db.session import SessionLocal, init_db
from app.rag.store import build_and_save_index
from app.services.chat_service import ChatService
from app.services.citations import extract_citation_ids
from app.tools.flashcard_tool import create_flashcard_tool
from app.tools.memory_tool import create_study_progress_tool
from app.tools.quiz_generator_tool import create_quiz_tool
from app.tools.rag_tool import create_rag_tool
from app.tools.recommendation_tool import create_recommendation_tool
from app.tools.study_planner_tool import create_study_planner_tool


class _OfflineEmbeddings(Embeddings):
    """Deterministic 3-gram bag-of-words embeddings; no network, no model."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    @staticmethod
    def _vec(text: str, dim: int = 64) -> list[float]:
        vec = [0.0] * dim
        clean = re.sub(r"\s+", " ", text.lower())
        for i in range(max(0, len(clean) - 2)):
            gram = clean[i : i + 3]
            bucket = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16) % dim
            vec[bucket] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


CHUNKS = [
    Document(
        page_content=(
            "Photosynthesis is the process by which green plants convert light "
            "energy into chemical energy. It occurs in the chloroplasts, using "
            "the pigment chlorophyll."
        ),
        metadata={"source": "photosynthesis_notes.pdf", "page": 3, "chunk_index": 0},
    ),
    Document(
        page_content=(
            "The light-dependent reactions happen in the thylakoid membranes and "
            "produce ATP and NADPH. Water is split, releasing oxygen as a by-product."
        ),
        metadata={"source": "photosynthesis_notes.pdf", "page": 4, "chunk_index": 1},
    ),
    Document(
        page_content=(
            "The Calvin cycle fixes carbon dioxide into glucose using the ATP and "
            "NADPH produced by the light reactions."
        ),
        metadata={"source": "photosynthesis_notes.pdf", "page": 7, "chunk_index": 2},
    ),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        user_id = f"cite_diag_{uuid4().hex[:8]}"
        crud.create_user(db, user_id=user_id, email=f"{user_id}@example.com",
                         hashed_password="x", display_name="Cite Diag")
        thread_id = f"cite_diag_{uuid4().hex[:8]}"
        crud.create_thread(db, thread_id=thread_id, title="Cite diag", user_id=user_id)
        doc_id = str(uuid4())
        index_dir = _SCRATCH / "index" / doc_id
        build_and_save_index(CHUNKS, _OfflineEmbeddings(), str(index_dir))
        crud.create_document(db, document_id=doc_id, thread_id=thread_id,
                             filename="photosynthesis_notes.pdf",
                             vectorstore_path=str(index_dir), page_count=3, chunk_count=3)
        db.commit()

        llm = create_llm()
        quiz_llm = create_quiz_llm()
        checkpointer = create_checkpointer(_SCRATCH / "checkpoints.db")
        embeddings = _OfflineEmbeddings()
        tools = [
            create_rag_tool(embeddings),
            create_quiz_tool(quiz_llm, embeddings),
            create_flashcard_tool(quiz_llm, embeddings),
            create_study_planner_tool(quiz_llm),
            create_study_progress_tool(),
            create_recommendation_tool(),
        ]
        graph = create_graph(llm=llm, checkpointer=checkpointer, tools=tools)
        service = ChatService(graph, tools=tools)

        for turn, question in enumerate(
            ["Explain how photosynthesis works.",
             "Where in the cell does it happen, and what does it produce?"],
            start=1,
        ):
            message, citations, _tool_results, _events = service.chat_with_tool_results(
                question, thread_id=thread_id, user_id=user_id
            )
            print(f"===== TURN {turn}: {question!r} =====")
            print("POST-SERVICE message repr (what the API client receives):")
            print(repr(message))
            print("  '[[cite' still present:", "[[cite" in message)
            print("  citations returned     :", citations)
            print()

            # Raw synthesis output, read from checkpointed graph state.
            state = graph.get_state({"configurable": {"thread_id": thread_id}})
            raw = None
            for m in reversed(state.values.get("messages", [])):
                if type(m).__name__ == "AIMessage" and not getattr(m, "tool_calls", None):
                    raw = m
                    break
            if raw is not None:
                content = raw.content
                text = str(content) if not isinstance(content, list) else "".join(
                    str(getattr(block, "text", block)) for block in content
                )
                print("RAW model output repr (before ChatService stripping):")
                print(repr(text))
                print("  content python type   :", type(content).__name__)
                print("  extract ids (regex)   :", extract_citation_ids(text))
            print()
    finally:
        db.close()
        close_checkpointer(checkpointer)
        shutil.rmtree(_SCRATCH, ignore_errors=True)


if __name__ == "__main__":
    main()
