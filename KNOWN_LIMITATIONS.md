# Known Limitations

References: [Project_Requirements.pdf](Project_Requirements.pdf) and [compact_prompt.md](compact_prompt.md). This document distinguishes intentional prototype tradeoffs, observed implementation gaps and unverified submission evidence. P5 is documentation-only and does not fix these items.

## Required environment and scope disclosures

| Limitation | Consequence |
|---|---|
| **Postgres, not SQLite** | Production deployment uses PostgreSQL, hosted on Supabase, not SQLite. SQLite is used only for local development and the test suite. SQLite's file-based storage does not survive the hosting platform's ephemeral disk, which wipes on every restart or redeploy; this would cause silent, random data loss in a live demo. SQLAlchemy's ORM abstraction makes the switch transparent to application code — this is an intentional dev/prod split, not an inconsistency. Locally, the backend also regenerates SQLite indexes on startup.

| **No OCR for scanned PDFs** | Image-only pages may yield no usable text. Upload a text-based PDF; do not expect scanned pages or diagrams to be understood visually. |
| **Cloud embeddings via Cohere, not a local model** | Uses Cohere's embed API (`embed-english-v3.0` by default, 1024-dim) behind `COHERE_API_KEY`; no local model memory and no first-use model download. Switching embedding models changes the FAISS vector dimensions, so existing indexes must be rebuilt (`python scripts/rebuild_vectorstore_embeddings.py`).  FAISS indexes live on the backend's local disk and do not survive a deployment restart or redeploy, so uploaded source PDFs must be re-ingested after a redeploy. Embedding calls leave the host for Cohere's API; combined with Groq generation, no stage of the RAG pipeline is fully offline.
| **Node-version issue blocks `npm run build`** | Production build is not verified in the reported environment. `npm run dev` works as reported by the owner. Use a compatible Node version and revalidate before deployment; P5 does not change the runtime or dependencies. |

## Documents and retrieval

- PDF is the supported material format. Non-PDF ingestion, OCR, image reasoning and comprehensive multimodal document understanding are not implemented by the current text pipeline.
- Structure-aware chunking helps retain table-like text but cannot guarantee accurate reconstruction of complex layouts, equations, tables or reading order.
- Figure/caption text retrieval is not visual inspection of a diagram.
- Bounded retrieval context can miss necessary evidence across pages. Broad queries may be refused even when relevant material exists.
- **Reranking disabled by default (deployment-scoped tradeoff):** The local BGE cross-encoder reranker (`BAAI/bge-reranker-base`) measures ~1.5GB resident once loaded and cannot fit Render's 512MB free tier, so reranking is OFF unless `RERANKING_ENABLED=true`. Without it, ranking uses dense/hybrid similarity alone and `rerank_score` is absent from results; retrieval precision is somewhat reduced (owner diagnostics previously reported near-zero reranker discrimination anyway, see [EVAL_WRITEUP.md](EVAL_WRITEUP.md)). Enable the flag only on instances with ≥2GB spare memory.
- The `0.35` threshold is a heuristic over the retrieval relevance score. It is not a calibrated correctness probability and requires revalidation after model/corpus changes.
- Exact figure-caption matches use a special retrieval path; one threshold does not establish support for every response.
- Source markers depend on model adherence and parsing. The saved evaluation includes an answer with citation-like prose but no returned sources.
- Embedding changes require compatible index rebuilding. Existing FAISS assets must not be assumed reusable across model substitutions.
- Local files, indexes and caches require persistent storage. In-memory caches are process-local, not a distributed cache.

## AI reliability, privacy and cost

- Groq generation depends on provider availability, valid model identifiers, quotas and network access. Temperature 0 reduces sampling variability but does not guarantee deterministic or correct answers.
- The quiz client does not explicitly set temperature; it need not behave identically to the chat client.
- Embedding calls leave the host for Cohere's API; combined with Groq generation, no stage of the RAG pipeline is fully offline.
- Optional LangSmith tracing may transmit prompts, outputs and metadata. Enable it deliberately and avoid sensitive material without appropriate consent.
- Pydantic validates structured shape and bounds, not factual accuracy, fairness or pedagogical quality.
- Prompt-based grounding and instruction separation are not complete defenses against prompt injection.
- General-chat routing exists alongside grounded-document behavior. A direct grounded-service test does not establish refusal behavior for every chat route.
- No comprehensive cost benchmark, token budget guarantee, multilingual evaluation or repeated-run reliability study is provided.

## Learning-loop scope

- EMA mastery is an estimate, not a validated assessment of competence. It starts at 50, depends on accepted evidence order, and has no time-based forgetting.
- Concept resolution at cosine similarity `0.88` can merge distinct concepts or split synonyms. Normalization is limited, especially for punctuation-heavy terms.
- Adaptive priority, difficulty bands and repeated-mistake detection are deterministic heuristics, not item-response theory or an optimized curriculum.
- Repeated mistakes mean three sub-60 scores within the latest ten attempts, not necessarily consecutive mistakes or a diagnosed misconception.
- Growth used by the recommendation helper compares recent assessment scores; it is not a longitudinal statistical analysis.
- Recommendations are truncated to the first three generated items, not globally ranked for usefulness.
- Grading/mastery/adaptation services and their tests do not by themselves demonstrate a fully connected open-ended browser assessment → persisted evidence → mastery → growth workflow. That integration requires separate end-to-end evidence.
- New mastery mutations remain application-internal; the exposed recommendation tool is read-only. This differs from the compact brief's requested ToolNode exposure for new mutation capabilities.

## Background processing and idempotency

Uploads now dispatch to a background worker (`app/services/ingestion_worker.py`): upload bytes are persisted to `backend/upload_media/` before the HTTP response returns, the upload endpoint answers immediately with a queued job, and the full `queued → processing → ready/failed` lifecycle executes on a worker thread. Retrying a failed job re-runs ingestion from the persisted upload media, and startup recovery re-enqueues jobs left queued by a restart.

Remaining constraints of that design:

- The worker is in-process and single-threaded. It survives proxy timeouts by construction, but it is not a distributed queue: a crash mid-processing leaves the job `processing` until a manual retry, and there is no automatic retry/backoff.
- Startup recovery covers `queued` jobs (and documents without job rows that have persisted media). A job that died mid-flight in `processing` is not auto-resumed.
- Upload media and FAISS indexes live on local disk; on ephemeral hosts (e.g. Render free tier) a redeploy can still lose the stored media for recovery, in which case the retry endpoint reports that the upload must be repeated.
- Unique event keys help avoid duplicates, but separate state/event commits are not an exactly-once transaction guarantee under crashes or concurrent requests.

These are limitations against PRD §§5, 12, 13 and 18, not features that should be inferred from the presence of job/event tables.

## Analytics and administration

- Dashboard/API surfaces expose useful prototype summaries, not every PRD admin filter, drill-down, user journey or evaluation-quality view.
- Some aggregates load records into memory rather than providing scalable paginated analytics.
- Global activity is filtered to the latest seven days, while AI-call counts in that response are all-time. They should not be interpreted as the same reporting window.
- Admin product “projects” counts distinct projects containing documents, not necessarily all created projects.
- Available usage/log fields are not proof that every AI feature populates measured tokens, cost, latency and failure status. In particular, the chat route initializes an AI-call record with latency 0; zero should not automatically be read as a measured zero-duration request.
- LangSmith is optional and separately configured; application aggregate views are not infrastructure monitoring.

## Security and operations

- Ownership checks and isolation tests are present, but no exhaustive security audit or penetration-test claim is made.
- **Progress/memory scoping (fixed):** `/progress`, the tutor's `get_study_progress` tool and the general-chat memory context now scope every read and write to the authenticated user **and** the active Project. A Project belongs to exactly one Space, so Project scoping also isolates Spaces. Legacy rows written before scoping carry `project_id = NULL` and are deliberately excluded from Project-scoped views rather than being shown everywhere.
- **Admin role restriction (fixed):** awarding admin status is deliberately harder than being a student. New admins are created only as the FIRST registered user, or via a direct database update (`make promote-admin`); there is no self-service admin-promote path.
- The JWT signing secret must be a strong deployment-provided value (≥ 32 bytes for HS256). When `SECRET_KEY` is unset the app generates an ephemeral key (logins stop validating after restart); a short configured value is deterministically padded with a loud warning — set a real secret in production.
- The legacy seeded `default_user` is not a documented usable login account.
- The dedicated Admin Console is not inherited: admins surface here and nowhere else, rather than being given their own study workspace.
- Protect database/index files and backups; do not expose local serialized index assets or accept untrusted prebuilt indexes.
- Rate limits, upload resource limits, secret rotation, retention/deletion policy, production TLS and robust operational recovery require deployment-specific review.
- The Vite development proxy is not production API routing. A deployed frontend needs a corresponding backend route/proxy configuration.
- Dependencies include broad minimum/range versions; installation behavior can drift. This phase did not execute a clean installation or resolve package compatibility.

## Evaluation and submission evidence

- The project owner confirmed **193/193 backend tests passing** at P4 handoff.
- The inspected saved live result is **6/8**, not 8/8. Two cases returned insufficient evidence; some passing checks are only keyword/source-presence tests.
- The eight-case evaluation does not directly test grading, persisted recommendation history, document-embedded injection, browser workflows or production operations. See [EVAL_WRITEUP.md](EVAL_WRITEUP.md).
- No tests, live evaluation, API calls or builds were rerun for P5.
- Fresh-clone setup is documented from source, not verified by running a fresh clone in this phase.
- Public application URL, repository visibility and a PRD §20 demo video are not verified by this documentation work. The existing project GIF is not asserted to be a complete current-submission demo.
- The available development prompt record is partial. Missing historical conversations are not reconstructed as fabricated “actual prompts.”
- Older `PROJECT_ARCHITECTURE.md` and `STUDYMATE_PROJECT_OVERVIEW.md` were left untouched; this P5 documentation set records current inspected details and explicit evidence boundaries.

## Higher-value follow-up work

After the documentation-only phase: validate the complete learning loop and deployment; make ingestion/retries durable; expand direct grading/recommendation and citation evaluation; populate measured telemetry consistently; then address storage scalability, migration tooling and optional OCR. These are future improvements, not completed changes.