"""
test_rag_manual.py
-------------------
Standalone manual test for the StudyMate RAG pipeline (Module 2) using Groq
as the LLM and NVIDIA's nv-embedqa-e5-v5 for embeddings. Not part of the
pytest suite - run this by hand to eyeball retrieval quality and inspect
the full trace in LangSmith.

Usage:
    python test_rag_manual.py --pdf ./sample.pdf --query "What is backpropagation?"
    python test_rag_manual.py --pdf ./sample.pdf --query "..." --hybrid
    python test_rag_manual.py --pdf ./sample.pdf --query "..." --no-rerank
    python test_rag_manual.py --pdf ./sample.pdf --query "..." --rebuild-index   # force a fresh index

Requires (in your .env, at the project root or backend/):
    GROQ_API_KEY=...
    NVIDIA_API_KEY=...              # from build.nvidia.com
    LANGSMITH_TRACING=true          # or LANGCHAIN_TRACING_V2=true (legacy name)
    LANGSMITH_API_KEY=...           # or LANGCHAIN_API_KEY
    LANGSMITH_PROJECT=studymate-dev # or LANGCHAIN_PROJECT

IMPORTANT: nv-embedqa-e5-v5 produces 1024-dim vectors vs. MiniLM's 384-dim.
Any existing index built with the old embeddings model is INCOMPATIBLE and
must be rebuilt - delete --index-path's directory before your first run
with this script, or you'll get a DocumentNotIndexedError from a dimension
mismatch.
"""

import os
import sys
import argparse
from pathlib import Path

# Force UTF-8 for Windows console printing
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

from langsmith import traceable
from langchain_groq import ChatGroq
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

# --- import paths: adjust only if your backend/app layout differs ---
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from app.rag.ingest import load_and_chunk_pdf
from app.rag.store import build_and_save_index, load_index, load_index_metadata, delete_index
from app.rag.retriever import retrieve
# ---------------------------------------------------------------------

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """
You are StudyMate, an AI study assistant.

Your job is to answer the user's question using ONLY the provided context.

Rules:
1. Never use your own knowledge.
2. If the context does not contain enough information, clearly say:
   "The provided context does not contain enough information to answer this question."
3. Before using information from a retrieved chunk, verify that the chunk is about the same topic, algorithm, or model that the user asked about.
4. If a retrieved chunk discusses a different algorithm or model (for example, the user asks about neural networks but the chunk discusses decision trees or gradient boosting), do NOT present that information as if it answers the user's question.
5. You may mention unrelated information only if you explicitly label it as being about a different algorithm.
6. Prefer the most relevant retrieved chunks over less relevant ones.
7. Do not combine unrelated chunks to create an answer.
8. If the answer comes from multiple chunks, combine only information that is consistent and refers to the same topic.

Answer clearly and concisely.
"""

# Embeddings must be instantiated exactly once, per store.py's own docstring
# warning - never construct this per-call. NVIDIAEmbeddings automatically
# uses input_type="passage" for embed_documents() and input_type="query"
# for embed_query() under the hood - no extra config needed here.
_EMBEDDINGS = NVIDIAEmbeddings(
    model="nvidia/nv-embedqa-e5-v5",
    api_key=os.getenv("NVIDIA_API_KEY"),
    truncate="END",
)


def build_context_block(chunks) -> str:
    """
    Turn retrieved RetrievedChunk objects into a numbered context block.
    Note: RetrievedChunk exposes .content/.source/.page directly - it is a
    Pydantic model, not a LangChain Document, so there is no .metadata dict.
    """
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[{i}] (source: {chunk.source}, page: {chunk.page}, "
            f"similarity: {chunk.similarity_score:.3f}"
            + (f", rerank: {chunk.rerank_score:.3f}" if chunk.rerank_score is not None else "")
            + f")\n{chunk.content}"
        )
    return "\n\n".join(parts)


@traceable(run_type="chain", name="get_or_build_index")
def get_or_build_index(pdf_path: str, index_path: str, force_rebuild: bool = False):
    """
    Ensure a FAISS index (+ persisted chunks for hybrid search) exists on
    disk at index_path, building it from the PDF if needed.

    Reusing a stale index (built from a *different* PDF, or from an older
    version of the same filename) is the #1 cause of confusing results:
    retrieval and reranking both "succeed" but return chunks about the
    wrong topic entirely, with no exception raised anywhere. So before
    reusing anything on disk, this checks the persisted index_metadata.json
    to make sure its recorded source filename(s) actually include the PDF
    you just asked to query - and rebuilds automatically if not.
    """
    pdf_name = Path(pdf_path).name
    index_exists = Path(index_path).exists()

    if force_rebuild and index_exists:
        print(f"[index] --rebuild-index passed, deleting existing index at {index_path}")
        delete_index(index_path)
        index_exists = False

    if index_exists:
        metadata = load_index_metadata(index_path)
        if metadata is None:
            print(f"[index] existing index found at {index_path} (no metadata - "
                  f"pre-dates provenance tracking), will reuse it as-is")
            return

        sources = metadata.get("sources") or []
        if pdf_name not in sources:
            print(f"[index] WARNING: existing index at {index_path} was built from "
                  f"{sources!r}, which does NOT include the PDF you passed ({pdf_name!r}). "
                  f"Rebuilding from {pdf_path} instead of silently querying the wrong "
                  f"document. Pass --index-path to point at a fresh directory, or "
                  f"--rebuild-index to force this each run.")
            delete_index(index_path)
        else:
            print(f"[index] existing index found at {index_path} "
                  f"(sources={sources}, chunks={metadata.get('chunk_count')}), will reuse it")
            return

    print(f"[index] no existing index found, building from {pdf_path}")
    pdf_bytes = Path(pdf_path).read_bytes()
    chunks, metadata_summary = load_and_chunk_pdf(
        pdf_bytes,
        filename=Path(pdf_path).name,
        chunk_size=700,
        chunk_overlap=150,
    )
    print(f"[index] chunked into {metadata_summary['chunk_count']} pieces "
          f"across {metadata_summary['page_count']} page(s)")

    build_and_save_index(chunks, _EMBEDDINGS, index_path)
    print(f"[index] saved to {index_path}")


@traceable(run_type="llm", name="groq_answer_with_context")
def answer_with_groq(query: str, context: str) -> str:
    llm = ChatGroq(model=GROQ_MODEL, temperature=0)
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"Context:\n{context}\n\nQuestion: {query}"),
    ]
    response = llm.invoke(messages)
    return response.content


@traceable(run_type="chain", name="manual_rag_test_run")
def run_manual_test(
    pdf_path: str,
    query: str,
    index_path: str,
    k: int,
    rerank_top_k: int,
    use_reranking: bool,
    use_hybrid_search: bool,
    force_rebuild: bool = False,
):
    """
    Root trace. Everything called inside here (index build/load, retrieve,
    rerank, groq call) nests under this single span in LangSmith.
    """
    get_or_build_index(pdf_path, index_path, force_rebuild=force_rebuild)

    chunks = retrieve(
        query,
        save_path=index_path,
        embeddings=_EMBEDDINGS,
        use_reranking=use_reranking,
        use_hybrid_search=use_hybrid_search,
        k=k,
        rerank_top_k=rerank_top_k,
    )
    mode = "hybrid (BM25+dense)" if use_hybrid_search else "pure dense"
    print(f"\n[retrieve] got {len(chunks)} chunk(s) for: {query!r}  [mode: {mode}]\n")
    for i, chunk in enumerate(chunks, start=1):
        preview = chunk.content[:500].replace("\n", " ")
        score_label = (
            f"rerank={chunk.rerank_score:.3f}"
            if chunk.rerank_score is not None
            else f"score={chunk.similarity_score:.3f}"
        )
        print(f"  [{i}] ({score_label}, source={chunk.source}, page={chunk.page}) {preview}...")

    context = build_context_block(chunks)
    answer = answer_with_groq(query, context)

    print("\n" + "=" * 60)
    print("ANSWER:")
    print(answer)
    print("=" * 60)

    return {"query": query, "num_chunks": len(chunks), "answer": answer}


def main():
    parser = argparse.ArgumentParser(description="Manual RAG pipeline test (Groq + LangSmith)")
    parser.add_argument("--pdf", required=True, help="Path to a source PDF")
    parser.add_argument("--query", required=True, help="Question to ask")
    parser.add_argument("--index-path", default="./vectorstores/manual_test_index", help="FAISS index directory")
    parser.add_argument("--k", type=int, default=6, help="Number of candidates fetched before reranking")
    parser.add_argument("--rerank-top-k", type=int, default=4, help="Number of final chunks returned when reranking is on")
    parser.add_argument("--no-rerank", action="store_true", help="Disable cross-encoder reranking")
    parser.add_argument("--hybrid", action="store_true", help="Enable BM25 + dense hybrid retrieval (Reciprocal Rank Fusion)")
    parser.add_argument("--rebuild-index", action="store_true",
                         help="Delete and rebuild the index at --index-path even if one already exists there")
    args = parser.parse_args()

    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not set in environment/.env")
        sys.exit(1)

    if not os.getenv("NVIDIA_API_KEY"):
        print("ERROR: NVIDIA_API_KEY not set in environment/.env (get one at build.nvidia.com)")
        sys.exit(1)

    if not Path(args.pdf).exists():
        print(f"ERROR: PDF not found at {args.pdf}")
        sys.exit(1)

    tracing_on = os.getenv("LANGSMITH_TRACING") or os.getenv("LANGCHAIN_TRACING_V2")
    if not tracing_on:
        print("WARNING: LANGSMITH_TRACING / LANGCHAIN_TRACING_V2 not set - this run won't be traced.")

    run_manual_test(
        args.pdf,
        args.query,
        args.index_path,
        args.k,
        args.rerank_top_k,
        use_reranking=not args.no_rerank,
        use_hybrid_search=args.hybrid,
        force_rebuild=args.rebuild_index,
    )


if __name__ == "__main__":
    main()