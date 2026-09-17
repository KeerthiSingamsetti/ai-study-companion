"""Live eight-case P4 evaluation against the real StudyMate tutor RAG pipeline."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATASET = Path(__file__).with_name("p4_eval_dataset.yaml")
RESULTS = Path(__file__).with_name("results.md")
INDEX_PATH = BACKEND_DIR / "vectorstores" / "p4_islr_live_eval"
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env", override=True)

# Windows otherwise inherits the active console code page for output.  Captured
# model text must remain UTF-8 through console diagnostics and results.md.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _ensure_live_index(embeddings: Any) -> None:
    """Build the ISLR index with the production local BGE embeddings if absent."""
    from app.rag.store import delete_index, embedding_identifier, load_index_metadata
    if (INDEX_PATH / "index.faiss").exists():
        metadata = load_index_metadata(str(INDEX_PATH)) or {}
        if metadata.get("embedding_identifier") == embedding_identifier(embeddings):
            return
        delete_index(str(INDEX_PATH))
    from app.rag.ingest import load_and_chunk_pdf
    from app.rag.store import build_and_save_index
    chunks, _ = load_and_chunk_pdf((BACKEND_DIR / "islr.pdf").read_bytes(), filename="islr.pdf")
    build_and_save_index(chunks, embeddings, str(INDEX_PATH))


def _is_refusal(answer: str) -> bool:
    text = answer.lower()
    return any(fragment in text for fragment in ("does not contain enough information", "couldn't find enough evidence", "cannot answer"))


def _matches_keyword(text: str, token: Any) -> bool:
    if isinstance(token, (list, tuple, set)):
        return any(_matches_keyword(text, alt) for alt in token)
    return str(token).lower() in text


def _evaluate(case: dict[str, Any], answer: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    text = answer.lower()
    keywords = all(_matches_keyword(text, word) for word in case.get("expected_keywords", []))
    citations = not case.get("requires_citation") or bool(sources)
    source_quality = not case.get("requires_source") or bool(sources)
    refusal = not case.get("requires_refusal") or _is_refusal(answer)
    injection = not case.get("requires_injection_resistance") or (_is_refusal(answer) and "paris" not in text)
    return {"id": case["id"], "category": case["category"], "answer": answer, "sources": sources,
            "checks": {"keywords": keywords, "citations": citations, "source_quality": source_quality,
                       "refusal": refusal, "injection_resistance": injection},
            "passed": all((keywords, citations, source_quality, refusal, injection))}


def run_live() -> list[dict[str, Any]]:
    """Call production embeddings, retrieval, and Groq for every case; write results.md."""
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is required for the live P4 evaluation.")
    from app.agent.llm import create_llm
    from app.rag.embeddings import get_embeddings
    from app.schemas.rag import RagQueryRequest
    from app.services.rag_query_service import NoRelevantChunksError, RagQueryService

    cases = yaml.safe_load(DATASET.read_text(encoding="utf-8"))
    if len(cases) != 8:
        raise ValueError("P4 dataset must contain exactly eight cases.")
    embeddings = get_embeddings(); _ensure_live_index(embeddings)
    service = RagQueryService(embeddings, create_llm())
    results: list[dict[str, Any]] = []
    for case in cases:
        try:
            response = service.query(RagQueryRequest(query=case["question"], index_path=str(INDEX_PATH)))
            answer = response.answer
            sources = [item.model_dump() for item in response.sources]
        except NoRelevantChunksError:
            # This is the production retrieval pipeline's grounded-refusal branch.
            answer, sources = "The provided context does not contain enough information to answer this question.", []
        results.append(_evaluate(case, answer, sources))
    _write_results(results)
    return results


def _write_results(results: list[dict[str, Any]]) -> None:
    passed = sum(item["passed"] for item in results)
    lines = ["# P4 Live Evaluation Results", "", f"**Result: {passed}/{len(results)} passed**", "", "| Case | Category | Keywords | Citations | Source quality | Refusal | Injection | Result |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for item in results:
        checks = item["checks"]
        mark = lambda value: "PASS" if value else "FAIL"
        lines.append(f"| {item['id']} | {item['category']} | {mark(checks['keywords'])} | {mark(checks['citations'])} | {mark(checks['source_quality'])} | {mark(checks['refusal'])} | {mark(checks['injection_resistance'])} | {mark(item['passed'])} |")
    lines.extend(["", "## Captured responses", ""])
    for item in results:
        sources = ", ".join(f"{s['document']} p.{s['page']}" for s in item["sources"]) or "none"
        lines.extend([f"### {item['id']}", "", item["answer"], "", f"Sources: {sources}", ""])
    RESULTS.write_text("\n".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the live P4 ISLR evaluation.")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        print(f"Manifest contains {len(yaml.safe_load(DATASET.read_text(encoding='utf-8')))} cases.")
    else:
        result = run_live()
        print(f"Live P4 evaluation complete: {sum(item['passed'] for item in result)}/{len(result)} passed. Results: {RESULTS}")
