# Known Limitations

References: [Project_Requirements.pdf](Project_Requirements.pdf) and [compact_prompt.md](compact_prompt.md). This document distinguishes intentional prototype tradeoffs, observed implementation gaps and unverified submission evidence. P5 is documentation-only and does not fix these items.

## Required environment and scope disclosures

| Limitation | Consequence |
|---|---|
| **SQLite, not Postgres** | Suitable for a local prototype; concurrent writes, multi-instance deployment and migrations need more work. SQLAlchemy configuration alone does not establish tested Postgres support. |
| **No OCR for scanned PDFs** | Image-only pages may yield no usable text. Upload a text-based PDF; do not expect scanned pages or diagrams to be understood visually. |
| **Local embeddings via sentence-transformers, not a cloud API** | Uses `BAAI/bge-small-en-v1.5`; no NVIDIA credential is needed. First-use downloads and host CPU/RAM/cold-start costs remain. |
| **Node-version issue blocks `npm run build`** | Production build is not verified in the reported environment. `npm run dev` works as reported by the owner. Use a compatible Node version and revalidate before deployment; P5 does not change the runtime or dependencies. |

## Documents and retrieval

- PDF is the supported material format. Non-PDF ingestion, OCR, image reasoning and comprehensive multimodal document understanding are not implemented by the current text pipeline.
- Structure-aware chunking helps retain table-like text but cannot guarantee accurate reconstruction of complex layouts, equations, tables or reading order.
- Figure/caption text retrieval is not visual inspection of a diagram.
- Bounded retrieval context can miss necessary evidence across pages. Broad queries may be refused even when relevant material exists.
- **Phrasing-sensitive local-model retrieval:** Prior diagnostics reported by the owner found near-zero reranker discrimination (scores around 0.5000) for `retrieval_relevance` and `assessment_equivalent_wording`, reducing retrieval precision in the substituted local embedding/reranking pipeline; this is documented as a model limitation, not a code bug, behind the saved 6/8 result (see [EVAL_WRITEUP.md](EVAL_WRITEUP.md)).
- The `0.35` threshold is a heuristic over the retrieval relevance score. It is not a calibrated correctness probability and requires revalidation after model/corpus changes.
- Exact figure-caption matches use a special retrieval path; one threshold does not establish support for every response.
- Source markers depend on model adherence and parsing. The saved evaluation includes an answer with citation-like prose but no returned sources.
- Embedding changes require compatible index rebuilding. Existing FAISS assets must not be assumed reusable across model substitutions.
- Local files, indexes and caches require persistent storage. In-memory caches are process-local, not a distributed cache.

## AI reliability, privacy and cost

- Groq generation depends on provider availability, valid model identifiers, quotas and network access. Temperature 0 reduces sampling variability but does not guarantee deterministic or correct answers.
- The quiz client does not explicitly set temperature; it need not behave identically to the chat client.
- Local embeddings do not make the product fully offline. Selected material, prompts and conversation context can leave the host for Groq generation.
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

The current document upload route invokes ingestion **inline**, then records a ready job after success. It does not dispatch the PDF to a durable background worker.

- Job states exist, but they do not establish that the complete `queued → processing → ready/failed` lifecycle executes asynchronously.
- Retry changes a failed record to queued and increments its count; it does not by itself restart processing.
- An upload failure before successful ingestion may occur before a job record is created.
- Worker recovery after a process restart, browser-independent durable execution and distributed retry/backoff are not established.
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
- **Legacy progress isolation gap:** `/progress`, `/progress/quiz-result` and `/progress/flashcard-result` still use `DEFAULT_USER_ID` rather than the authenticated user and selected project, violating the PRD's isolation requirement; remediation is deferred as a non-blocking follow-up before final submission if time permits.
- The development JWT signing-secret fallback must be replaced with a strong secret. The README explicitly requires `SECRET_KEY`.
- The legacy seeded `default_user` is not a documented usable login account.
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

## Highest-value follow-up work

After the documentation-only phase: validate the complete learning loop and deployment; make ingestion/retries durable; expand direct grading/recommendation and citation evaluation; populate measured telemetry consistently; then address storage scalability, migration tooling and optional OCR. These are future improvements, not completed changes.