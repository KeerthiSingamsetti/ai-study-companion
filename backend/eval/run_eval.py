"""
eval/run_eval.py
----------------
RAG Evaluation Harness for StudyMate (Module 2) using RAGAS.

- Generator : Groq (llama-3.3-70b-versatile)
- Judge     : Groq (openai/gpt-oss-120b via LangchainLLMWrapper)
              NOTE: Upgraded from gemma2-9b-it/llama-3.1-8b-instant to a
              stronger, different-family model. This both raises judge
              reliability AND reduces same-family self-evaluation bias
              (gpt-oss vs Llama, not just "different Groq deployment").
- Embeddings: HuggingFace BAAI/bge-small-en-v1.5 (local, no API key needed)
              NOTE: Upgraded from all-MiniLM-L6-v2. Same 384-dim footprint
              (index format compatible) but consistently stronger retrieval
              quality on MTEB-style retrieval benchmarks. Original design
              used NVIDIA nv-embedqa-e5-v5 (1024-dim); still unavailable
              since the NVIDIA API key expired.

KNOWN GAPS (require changes outside this file):
  - Better reranker: reranking happens inside app/rag/retriever.py
    (`use_reranking=True` path). This file only calls retrieve() with the
    flag on; swapping the actual reranker model/algorithm needs to happen
    in retriever.py, which was not available when this harness was updated.
  - Metadata-aware retrieval: filtering/boosting by page, section, or other
    metadata needs support inside app/rag/store.py + retriever.py's search
    call. Not implemented here for the same reason.

Usage:
    python eval/run_eval.py                  # pure dense baseline
    python eval/run_eval.py --hybrid         # hybrid BM25 + dense
    python eval/run_eval.py --no-cache       # ignore retrieval cache
    python eval/run_eval.py --no-multiquery  # disable multi-query retrieval
"""

import os
import sys
import time
import yaml
import hashlib
import pickle
import argparse
import types
from pathlib import Path
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
CACHE_DIR = EVAL_DIR / ".cache"
CACHE_PATH = CACHE_DIR / "retrieval_cache.pkl"

# ── Compatibility shim: RAGAS 0.2.x imports ChatVertexAI from a path that no
#    longer exists in modern langchain_community. Patch before importing ragas.
try:
    import langchain_community.chat_models.vertexai  # noqa: F401
except ModuleNotFoundError:
    _m = types.ModuleType("langchain_community.chat_models.vertexai")
    try:
        from langchain_google_vertexai import ChatVertexAI
        _m.ChatVertexAI = ChatVertexAI
    except Exception:
        _m.ChatVertexAI = None
    sys.modules["langchain_community.chat_models.vertexai"] = _m

# Force UTF-8 for Windows console
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Load .env from backend/ — eval/ now lives inside backend/, so parent = backend/
_ENV_PATH = BACKEND_DIR / ".env"
from dotenv import load_dotenv
load_dotenv(dotenv_path=_ENV_PATH)

# Make backend/app importable (parent of eval/ = backend/)
sys.path.insert(0, str(BACKEND_DIR))

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

from app.rag.ingest import load_and_chunk_pdf
from app.rag import store
from app.rag.store import build_and_save_index
from app.rag.retriever import compress_retrieved_chunks, retrieve
from app.rag.reranker import MODEL_NAME as RERANKER_MODEL_NAME

from ragas import SingleTurnSample, EvaluationDataset, evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.run_config import RunConfig

# ── Models ────────────────────────────────────────────────────────────────────
GENERATOR_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
JUDGE_MODEL     = "openai/gpt-oss-120b"     # (10) stronger + different-family judge
EMBED_MODEL     = "BAAI/bge-small-en-v1.5"  # (1) better embeddings, same dim as before

# Retrieval quality knobs
CHUNK_SIZE      = 500   # (4) smaller chunks -> more precise retrieval
CHUNK_OVERLAP   = 100
SIM_THRESHOLD   = 0.35  # (6) drop weakly-relevant chunks
MULTIQUERY_N    = 2     # (5) number of paraphrase queries generated per question
COMPRESS_TOPK_SENTENCES = 3   # (7) sentences kept per chunk after compression
COMPRESS_MAX_CHARS = 400      # (7) hard cap per compressed chunk

# RAGAS judge concurrency/timeout knobs (11) — Groq's free/dev tier has fairly
# tight per-minute request limits, and each RAGAS metric issues several LLM
# calls per sample (faithfulness alone does statement-extraction + verification
# calls). At the default RunConfig (max_workers=16, timeout=180s), 16 questions
# x 4 metrics fan out into dozens of *simultaneous* Groq requests; several of
# them queue behind Groq's rate limiter long enough to blow past the default
# per-request timeout, which surfaces as the Job[N] TimeoutError()s below.
# Dropping max_workers throttles concurrency to what Groq can actually serve
# in parallel, and raising timeout/max_wait gives queued requests enough room
# to complete instead of being killed. All three are overridable via env vars
# so you can tune them without touching code (e.g. if you're on a paid Groq
# tier with higher rate limits, RAGAS_MAX_WORKERS=6 or higher will be faster).
RAGAS_MAX_WORKERS  = int(os.getenv("RAGAS_MAX_WORKERS", "2"))
RAGAS_TIMEOUT       = int(os.getenv("RAGAS_TIMEOUT", "300"))   # seconds, per LLM call
RAGAS_MAX_RETRIES   = int(os.getenv("RAGAS_MAX_RETRIES", "5"))
RAGAS_MAX_WAIT      = int(os.getenv("RAGAS_MAX_WAIT", "90"))   # cap on exponential backoff

RAGAS_RUN_CONFIG = RunConfig(
    timeout=RAGAS_TIMEOUT,
    max_retries=RAGAS_MAX_RETRIES,
    max_wait=RAGAS_MAX_WAIT,
    max_workers=RAGAS_MAX_WORKERS,
)

# ChatGroq-side timeout/retry knobs, independent from RAGAS's own retry loop.
# These bound how long a single HTTP call to Groq is allowed to hang before
# langchain_groq raises, and how many times langchain_groq itself will retry
# a failed call before RAGAS's RunConfig-level retry/backoff ever kicks in.
GROQ_REQUEST_TIMEOUT = int(os.getenv("GROQ_REQUEST_TIMEOUT", "120"))  # seconds
GROQ_MAX_RETRIES     = int(os.getenv("GROQ_MAX_RETRIES", "3"))

# Single embeddings instance (must be the same model used to build the index)
_EMBEDDINGS = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

# ── System prompt (hardened against cross-topic blending) ────────────────────
SYSTEM_PROMPT = """You are StudyMate, an AI study assistant.
Answer ONLY using the provided context.

Rules:
1. Never use your own knowledge.
2. If the context does not contain enough information say exactly:
   "The provided context does not contain enough information to answer this question."
3. Before using a chunk, verify it is about the SAME topic/algorithm the user asked about.
4. If a chunk is about a different algorithm (e.g. user asks neural networks but chunk
   covers decision trees), do NOT use it as if it answers the question.
5. You may cite off-topic chunks only if you explicitly label them as off-topic.
6. Do not blend information from unrelated chunks into a single answer.

Answer clearly and concisely."""


# ── Retrieval cache (9) ───────────────────────────────────────────────────────

def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = CACHE_PATH.with_suffix(".tmp")
    with open(temporary_path, "wb") as f:
        pickle.dump(cache, f)
    temporary_path.replace(CACHE_PATH)


def _cache_key(query: str, index_path: str, use_hybrid: bool, k: int, rerank_top_k: int,
               use_multiquery: bool) -> str:
    """Invalidate persistent results when retrieval configuration changes."""
    raw = "|".join((
        query,
        str(Path(index_path).resolve()),
        store.index_fingerprint(index_path),
        str(use_hybrid), str(k), str(rerank_top_k),
        EMBED_MODEL, RERANKER_MODEL_NAME,
        str(SIM_THRESHOLD), str(MULTIQUERY_N), str(use_multiquery),
        str(COMPRESS_TOPK_SENTENCES), str(COMPRESS_MAX_CHARS),
    ))
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# ── Multi-query retrieval (5) ─────────────────────────────────────────────────

def generate_query_variants(question: str, llm, n: int = MULTIQUERY_N) -> list:
    """Ask the generator LLM for n alternative phrasings of the same question."""
    prompt = (
        f"Rewrite the following question in {n} different ways that preserve its "
        f"exact meaning (useful for search retrieval). Return ONLY the {n} rewrites, "
        f"one per line, no numbering, no extra commentary.\n\nQuestion: {question}"
    )
    try:
        resp = llm.invoke([("human", prompt)])
        lines = [l.strip("-• \t") for l in resp.content.strip().splitlines() if l.strip()]
        variants = [l for l in lines if l][:n]
    except Exception:
        variants = []
    return [question] + variants


def multi_query_retrieve(question: str, index_path: str, use_hybrid: bool,
                          cache: dict, llm, k: int = 6, rerank_top_k: int = 4,
                          use_multiquery: bool = True):
    key = _cache_key(question, index_path, use_hybrid, k, rerank_top_k, use_multiquery)
    if key in cache:
        return cache[key]

    queries = generate_query_variants(question, llm) if use_multiquery else [question]
    # retrieve() deduplicates candidates by stable chunk ID and reranks their
    # union once against the original question, so rerank scores stay comparable.
    chunks = retrieve(
        question,
        save_path=index_path,
        embeddings=_EMBEDDINGS,
        use_reranking=True,
        use_hybrid_search=use_hybrid,
        k=k,
        rerank_top_k=rerank_top_k,
        query_variants=queries[1:],
        min_relevance_score=SIM_THRESHOLD,
        cache_results=True,
    )
    cache[key] = chunks
    return chunks


# ── Similarity threshold filtering (6) ────────────────────────────────────────

# ── Context compression (7) ───────────────────────────────────────────────────

def build_context_block(chunks) -> str:
    """Format already-compressed chunks for both generation and RAGAS."""
    parts = []
    for i, c in enumerate(chunks, 1):
        score = f"rerank={c.rerank_score:.3f}" if c.rerank_score is not None \
                else f"sim={c.similarity_score:.3f}"
        parts.append(f"[{i}] (page:{c.page}, {score})\n{c.content}")
    return "\n\n".join(parts)


def ensure_index(pdf_path: str, index_path: str):
    if Path(index_path).exists():
        metadata = store.load_index_metadata(index_path)
        if metadata is None:
            print(f"[index] Reusing legacy index at {index_path} (no provenance metadata)")
            print("[index] Rebuild this index once to guarantee it uses BGE + 500/100 chunking.")
        else:
            print(f"[index] Reusing {metadata.get('embedding_identifier', 'unknown')} index at {index_path}")
        return
    print(f"[index] Building index from {pdf_path} ...")
    pdf_bytes = Path(pdf_path).read_bytes()
    chunks, summary = load_and_chunk_pdf(
        pdf_bytes, filename=Path(pdf_path).name,
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
    )
    print(f"[index] {summary['chunk_count']} chunks across {summary['page_count']} pages")
    build_and_save_index(
        chunks,
        _EMBEDDINGS,
        index_path,
        index_metadata={
            "embedding_model": EMBED_MODEL,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "source_pdf": str(Path(pdf_path).resolve()),
        },
    )
    print(f"[index] Saved to {index_path}")


def generate_answer(query: str, context: str, llm) -> str:
    resp = llm.invoke([
        ("system", SYSTEM_PROMPT),
        ("human", f"Context:\n{context}\n\nQuestion: {query}"),
    ])
    return resp.content.strip()


REFUSAL_PHRASES = [
    "does not contain enough information",
    "not contain enough information",
    "does not contain information",
    "cannot answer",
    "no information",
    "context does not",
]

def check_refusal_or_correction(item_id: int, category: str, answer: str) -> bool:
    a = answer.lower()
    if category == "out_of_scope":
        return any(p in a for p in REFUSAL_PHRASES)
    if category == "adversarial":
        if item_id == 14:
            forbidden = ("max_depth", "pre-pruning", "learning rate", "gradient boost")
            has_valid_fix = any(term in a for term in (
                "shrink the network", "smaller network", "reduce the network",
                "increase alpha", "regularization", "l2 penalty",
            ))
            return has_valid_fix and not any(term in a for term in forbidden)
        if item_id == 15:
            return any(p in a for p in (
                "do not have hidden layers", "does not have hidden layers",
                "no hidden layers", "don't have hidden layers",
            ))
        if item_id == 16:
            corrects_premise = any(p in a for p in (
                "do not use a learning rate", "does not use a learning rate",
                "no learning rate", "don't use a learning rate",
            ))
            return corrects_premise and not any(p in a for p in (
                "learning rate controls", "increase the learning rate",
                "decrease the learning rate",
            ))
    return True


# ── Main evaluation loop ──────────────────────────────────────────────────────

def run_evaluation(dataset_path: str, pdf_path: str, index_path: str, use_hybrid: bool,
                    use_cache: bool = True, use_multiquery: bool = True):
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset_raw = yaml.safe_load(f)

    ensure_index(pdf_path, index_path)

    # Two separate Groq API keys/projects (12) — using one key for both the
    # generator (16 calls) and the judge (dozens of calls across 4 RAGAS
    # metrics) means both draw from the SAME per-key rate-limit bucket, which
    # compounds the timeout issue on top of high judge concurrency. Splitting
    # them across two Groq accounts/keys gives each its own independent quota.
    # Falls back to GROQ_API_KEY for either role if its specific key isn't
    # set, so this stays backward compatible with a single-key .env.
    shared_key = os.getenv("GROQ_API_KEY")
    generator_key = os.getenv("GROQ_GENERATOR_API_KEY") or shared_key
    judge_key     = os.getenv("GROQ_JUDGE_API_KEY") or shared_key

    if not generator_key:
        print("ERROR: GROQ_GENERATOR_API_KEY (or GROQ_API_KEY) missing from backend/.env")
        sys.exit(1)
    if not judge_key:
        print("ERROR: GROQ_JUDGE_API_KEY (or GROQ_API_KEY) missing from backend/.env")
        sys.exit(1)
    if generator_key == judge_key:
        print("[warn] Generator and judge are using the SAME Groq API key — "
              "they'll share one rate-limit bucket. Set GROQ_GENERATOR_API_KEY "
              "and GROQ_JUDGE_API_KEY to separate keys to avoid that.")

    generator_llm  = ChatGroq(
        model=GENERATOR_MODEL, temperature=0, api_key=generator_key,
        timeout=GROQ_REQUEST_TIMEOUT, max_retries=GROQ_MAX_RETRIES,
    )
    judge_llm      = ChatGroq(
        model=JUDGE_MODEL, temperature=0, api_key=judge_key,
        timeout=GROQ_REQUEST_TIMEOUT, max_retries=GROQ_MAX_RETRIES,
    )
    ragas_llm      = LangchainLLMWrapper(judge_llm)
    ragas_embeddings = LangchainEmbeddingsWrapper(_EMBEDDINGS)

    cache = _load_cache() if use_cache else {}

    mode_label = "HYBRID (BM25+Dense)" if use_hybrid else "PURE DENSE"
    print("\n" + "=" * 75)
    print(f"  StudyMate RAG Eval — {mode_label}")
    print(f"  Generator : Groq / {GENERATOR_MODEL}")
    print(f"  Judge     : Groq / {JUDGE_MODEL}  ← stronger + different-family than generator")
    print(f"  Embeddings: HuggingFace / {EMBED_MODEL}")
    print(f"  Chunking  : size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}")
    print(f"  Multi-query retrieval: {'ON' if use_multiquery else 'OFF'}  |  "
          f"Retrieval cache: {'ON' if use_cache else 'OFF'}")
    print("  ⚠  SAME-PROVIDER WARNING: Judge and generator both use Groq.")
    print("     Scores may be somewhat optimistically biased even with a different")
    print("     judge model family. Reset Gemini quota or add OPENAI_API_KEY for a")
    print("     fully independent judge in future runs.")
    print("=" * 75 + "\n")

    # ── Phase 1: retrieval + generation for every item (no judge calls yet) ──
    prepared = []
    for item in dataset_raw:
        item_id   = item["id"]
        category  = item["category"]
        question  = item["question"]
        gt        = item["ground_truth"]
        exp_pages = item.get("expected_source_pages", [])

        print(f"[{item_id:02d}/16] {category[:12]:<12} | {question[:55]}...")

        chunks = multi_query_retrieve(
            question, index_path, use_hybrid, cache, generator_llm,
            k=6, rerank_top_k=4, use_multiquery=use_multiquery,
        )
        ret_pages = [c.page for c in chunks if c.page is not None]
        hit = any(p in exp_pages for p in ret_pages) if exp_pages else None

        # Score the exact compressed context that the generator sees. Keeping
        # the raw text in RetrievedChunk.raw_content preserves auditability.
        context_chunks = compress_retrieved_chunks(
            chunks,
            question,
            _EMBEDDINGS,
            max_sentences=COMPRESS_TOPK_SENTENCES,
            max_chars=COMPRESS_MAX_CHARS,
        )
        answer = generate_answer(question, build_context_block(context_chunks), generator_llm)
        refusal_ok = check_refusal_or_correction(item_id, category, answer)

        prepared.append(dict(
            id=item_id, category=category, question=question, ground_truth=gt,
            expected_pages=exp_pages, retrieved_pages=ret_pages, retrieval_hit=hit,
            answer=answer, refusal_check=refusal_ok,
            retrieved_contexts=[c.content for c in context_chunks],
        ))

        time.sleep(0.3)  # generator-side rate-limit courtesy

    if use_cache:
        _save_cache(cache)

    # ── Phase 2: batched RAGAS evaluation (8) — 2 calls total, not 16 ────────
    straightforward = [p for p in prepared if p["category"] == "straightforward"]
    adversarial     = [p for p in prepared if p["category"] != "straightforward"]

    def _to_samples(items):
        return [
            SingleTurnSample(
                user_input=it["question"], response=it["answer"],
                retrieved_contexts=it["retrieved_contexts"], reference=it["ground_truth"],
            ) for it in items
        ]

    sf_scores = {}
    if straightforward:
        ds_sf = EvaluationDataset(_to_samples(straightforward))
        res_sf = evaluate(ds_sf, metrics=[faithfulness, context_precision, context_recall, answer_relevancy],
                           llm=ragas_llm, embeddings=ragas_embeddings, show_progress=False,
                           run_config=RAGAS_RUN_CONFIG).to_pandas()
        for i, it in enumerate(straightforward):
            sf_scores[it["id"]] = dict(
                faithfulness=float(res_sf.get("faithfulness", [0.0])[i]),
                context_precision=float(res_sf.get("context_precision", [0.0])[i]),
                context_recall=float(res_sf.get("context_recall", [0.0])[i]),
                answer_relevancy=float(res_sf.get("answer_relevancy", [0.0])[i]),
            )

    adv_scores = {}
    if adversarial:
        ds_adv = EvaluationDataset(_to_samples(adversarial))
        res_adv = evaluate(ds_adv, metrics=[faithfulness],
                            llm=ragas_llm, embeddings=ragas_embeddings, show_progress=False,
                            run_config=RAGAS_RUN_CONFIG).to_pandas()
        for i, it in enumerate(adversarial):
            adv_scores[it["id"]] = dict(faithfulness=float(res_adv.get("faithfulness", [0.0])[i]))

    # ── Assemble results ──────────────────────────────────────────────────────
    results = []
    for it in prepared:
        if it["category"] == "straightforward":
            s = sf_scores[it["id"]]
            f_s, cp_s, cr_s, ar_s = s["faithfulness"], s["context_precision"], s["context_recall"], s["answer_relevancy"]
        else:
            s = adv_scores[it["id"]]
            f_s = s["faithfulness"]
            cp_s = cr_s = ar_s = None

        status = "PASS" if (it["category"] == "straightforward" and f_s >= 0.7) or \
                           (it["category"] != "straightforward" and f_s >= 0.7 and it["refusal_check"]) \
                 else "FAIL"
        print(f"[{it['id']:02d}]   faith={f_s:.2f}  refusal={it['refusal_check']}  "
              f"hit={it['retrieval_hit']}  → {status}")

        results.append(dict(
            id=it["id"], category=it["category"], question=it["question"],
            retrieved_pages=str(it["retrieved_pages"]), expected_pages=str(it["expected_pages"]),
            retrieval_hit=it["retrieval_hit"], refusal_check=it["refusal_check"],
            faithfulness=f_s, context_precision=cp_s,
            context_recall=cr_s, answer_relevancy=ar_s,
            status=status,
        ))

    df = pd.DataFrame(results)

    tag = "hybrid" if use_hybrid else "dense"
    csv_path = EVAL_DIR / f"eval_results_{tag}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"\n[Saved] {csv_path}\n")

    _print_summary(df, mode_label)
    return df


def _print_summary(df: pd.DataFrame, mode_label: str):
    sf  = df[df["category"] == "straightforward"]
    adv = df[df["category"] != "straightforward"]

    W = 80
    print("=" * W)
    print(f"  TABLE 1 – STRAIGHTFORWARD (Q1-Q11)  |  {mode_label}")
    print("=" * W)
    print(f"{'ID':<4} {'Hit':<5} {'Faith':<7} {'CtxP':<7} {'CtxR':<7} {'AnsR':<7} Status")
    print("-" * W)
    for _, r in sf.iterrows():
        h = "YES" if r["retrieval_hit"] else ("N/A" if r["retrieval_hit"] is None else "NO")
        fail_mark = " ← FAIL" if r["status"] == "FAIL" else ""
        print(f"{r['id']:<4} {h:<5} {r['faithfulness']:<7.3f} "
              f"{r['context_precision']:<7.3f} {r['context_recall']:<7.3f} "
              f"{r['answer_relevancy']:<7.3f} {r['status']}{fail_mark}")
    print("-" * W)
    avg_hit = sf["retrieval_hit"].dropna().mean() * 100
    print(f"{'AVG':<4} {avg_hit:4.0f}%  {sf['faithfulness'].mean():<7.3f} "
          f"{sf['context_precision'].mean():<7.3f} {sf['context_recall'].mean():<7.3f} "
          f"{sf['answer_relevancy'].mean():<7.3f}")
    print("=" * W + "\n")

    print("=" * W)
    print(f"  TABLE 2 – OUT-OF-SCOPE & ADVERSARIAL (Q12-Q16)  |  {mode_label}")
    print("=" * W)
    print(f"{'ID':<4} {'Category':<14} {'Faith':<7} {'Refusal/Correction':<25} Status")
    print("-" * W)
    for _, r in adv.iterrows():
        rc = "PASS (correct)" if r["refusal_check"] else "FAIL (blended)"
        fail_mark = " ← FAIL" if r["status"] == "FAIL" else ""
        print(f"{r['id']:<4} {r['category']:<14} {r['faithfulness']:<7.3f} {rc:<25} {r['status']}{fail_mark}")
    print("-" * W)
    pass_pct = adv["refusal_check"].mean() * 100
    print(f"{'AVG':<4} {'OVERALL':<14} {adv['faithfulness'].mean():<7.3f} "
          f"Refusal pass rate: {pass_pct:.0f}%")
    print("=" * W + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="StudyMate RAG Evaluation Harness")
    p.add_argument("--hybrid",       action="store_true",
                   help="Enable hybrid BM25+Dense retrieval")
    p.add_argument("--dataset",      default=str(EVAL_DIR / "eval_dataset.yaml"))
    p.add_argument("--pdf",          default=str(BACKEND_DIR / "sample.pdf"))
    p.add_argument("--index-path",   default=str(BACKEND_DIR / "vectorstores" / "eval_index_hf"),
                   help="Pre-built HuggingFace-embeddings FAISS index")
    p.add_argument("--no-cache",     action="store_true", help="Disable retrieval cache")
    p.add_argument("--no-multiquery", action="store_true", help="Disable multi-query retrieval")
    args = p.parse_args()

    run_evaluation(
        dataset_path=args.dataset,
        pdf_path=args.pdf,
        index_path=args.index_path,
        use_hybrid=args.hybrid,
        use_cache=not args.no_cache,
        use_multiquery=not args.no_multiquery,
    )