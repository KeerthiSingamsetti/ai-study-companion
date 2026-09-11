"""Cached, low-cost document topic extraction for planning."""
from __future__ import annotations
import json
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from app.db import crud
from app.db.session import SessionLocal
from app.rag.store import load_chunks

def extract_document_topics(document_id: str, llm: Any, max_topics: int = 10) -> list[str]:
    """Return cached topics or infer them from evenly sampled persisted chunks.

    Ingestion has chunk positions but currently no heading/bookmark metadata, so
    structural extraction is intentionally a no-op pending ingest support.
    """
    db = SessionLocal()
    try:
        cached = crud.get_topics_cache(db, document_id)
        if cached:
            return json.loads(cached.topics_json)
        document = crud.get_document(db, document_id)
        if document is None:
            raise LookupError("The requested document does not exist.")
        chunks = sorted(load_chunks(document.vectorstore_path) or [], key=lambda c: c.metadata.get("chunk_index", 0))
        if not chunks:
            return []
        count = min(max_topics, len(chunks))
        sample = [chunks[round(i * (len(chunks) - 1) / max(count - 1, 1))].page_content for i in range(count)]
        response = llm.invoke([
            SystemMessage(content="Return ONLY a JSON array of concise major document topic strings."),
            HumanMessage(content="\n\n---\n\n".join(sample)),
        ])
        topics = json.loads(str(response.content))
        if not isinstance(topics, list) or not all(isinstance(topic, str) for topic in topics):
            raise ValueError("Topic extractor returned invalid JSON.")
        topics = topics[:max_topics]
        crud.save_topics_cache(db, document_id, json.dumps(topics))
        return topics
    finally:
        db.close()
