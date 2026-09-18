# Assumptions and Engineering Decisions

References: [Project_Requirements.pdf](Project_Requirements.pdf), especially §§7–15, 17–20, and [antigravity_prompt_compact.md](antigravity_prompt_compact.md). The PRD leaves providers and implementation choices open; the brief requires extending StudyMate.

This log separates implemented policy from empirical proof. Numerical settings below match the inspected code. Their rationale explains the prototype tradeoff, not a claim that a parameter sweep, educational study, or provider benchmark was performed.

## 1. Extend StudyMate, do not rewrite

**Decision:** Reuse the prior team project's FastAPI/LangGraph/RAG foundation and React study workspace.

**Reasoning:** A short prototype benefits more from adding ownership, grounding, learning evidence, and observability than replacing functioning orchestration. Existing regression tests reduce change risk. Reuse is explicitly disclosed rather than attributed entirely to this submission.

**Consequence:** Legacy names remain: a Project is represented by `Thread`, and some APIs use `thread_id`. A wholesale rename would risk checkpoint, document, and tool compatibility without adding user value.

## 2. Mastery EMA — 85% history, 15% new evidence

Implemented in `backend/app/services/mastery.py`, configured in `backend/app/config.py`:

```text
M0 = 50
Mt = round(0.85 * M(t-1) + 0.15 * Et, 2)
0 <= Mt, Et <= 100
```

- **Why 0.85/0.15:** Retain accumulated history while allowing a new result to change the estimate. One guessed answer or one unusually hard question should not reset a learner's standing.
- **Why initial 50:** A neutral midpoint rather than treating an unseen concept as either mastered or failed. It is a prior, not observed competence; show attempt counts alongside scores.
- **Recency meaning:** Recency is by accepted evidence order, not elapsed time. An evidence point's unrounded contribution after `k` later attempts is `0.15 * 0.85^k`. There is no automatic forgetting during inactivity.
- **Example:** Starting at 50, evidence of 100 produces 57.50; subsequent evidence of 0 produces 48.88.
- **Why two decimal places:** Stable, readable persisted values rather than exposing floating-point noise.
- **Validation:** Scores outside 0–100 are rejected. Reusing an accepted event key must not apply evidence twice.

This is a learning-support heuristic, not a psychometrically validated mastery probability. The formula consumes supplied evidence; its existence does not prove every quiz/UI path supplies that evidence.

## 3. Assessment evidence weights — 50% understanding, 50% accuracy

`OpenEndedGrade.overall_score`:

```text
E = round((understanding + accuracy) / 2, 2)
```

**Reasoning:** Understanding and factual accuracy are both necessary. Equal weights are transparent and avoid inventing a more detailed weighting scheme without labeled grading data.

The validated schema also requires covered/missing concept lists and nonempty feedback. The grader prompt accepts equivalent explanations and treats the reference as an exemplar, not an exact-match answer. Relevance and reasoning appear in the rubric but are not independently weighted numeric fields.

**Tradeoff:** A valid JSON grade can still be educationally wrong. Schema validity is necessary, not evidence of grading fairness or correctness.

## 4. Retrieval relevance cutoff — 0.35

`MIN_RELEVANCE_THRESHOLD = 0.35` is passed by the RAG tool and query service into retrieval.

**Exact scoring semantics:** In the reranked path, `relevance_score` is `sigmoid(raw_cross_encoder_logit)`, plus an optional metadata-preference boost, capped at 1. Raw `rerank_score` is retained separately. Candidates below 0.35 are discarded. Without reranking, bounded dense or normalized reciprocal-rank-fusion scores are used instead; those scales are not interchangeable.

**Reasoning:** Require a minimum evidence signal while retaining moderately relevant passages that might be excluded by a stricter gate. Empty retrieval is a valid outcome that supports explicit refusal instead of forced generation.

**Important qualifications:**

- 0.35 is not a “35% chance the answer is correct.”
- Sigmoid bounds the score; it does not demonstrate statistical calibration.
- Metadata preferences have a default boost weight of 0.05 when supplied.
- Exact figure-caption matches are inserted through a separate special-case path with relevance 1.0; the cutoff is not a universal guarantee of semantic support.
- The saved live evaluation contains false refusals. This cutoff is not established as optimal and must be re-evaluated after changing corpus, embeddings, or reranker.

## 5. Concept-resolution threshold — 0.88

`resolve_concept` first normalizes names to lowercase alphanumeric tokens with collapsed whitespace and tries an exact match within the current project. If none exists, it chooses the highest cosine similarity among that project's concept embeddings and reuses the concept only when similarity is **at least 0.88**. Otherwise it creates a new concept.

**Reasoning:** Exact matching is cheap and predictable. A relatively high semantic threshold reduces accidental merging of related but distinct concepts, which would contaminate mastery evidence. Duplicate synonyms are less damaging than silently combining different skills.

**Tradeoff:** Abbreviations, punctuation-heavy technical names, and paraphrases can still split or merge incorrectly. There is no labeled concept-resolution benchmark establishing 0.88 as optimal. The helper accepts an injected embedding client; current application embeddings are local BGE. Its legacy “NIM” docstring is not evidence of a live NVIDIA call.

## 6. Adaptive selection, mistakes, and growth

Implemented in `learning.py` and `recommendation_tool.py`:

| Policy | Setting | Reasoning and boundary |
|---|---|---|
| Concept priority | `(100 − mastery) + 12 × recent_mistake_count` | Combine knowledge gap with recurring difficulty; each mistake contributes a visible 12-point urgency bonus rather than flipping difficulty based on one answer. This weight is heuristic. |
| Difficulty | Easy below 45; medium from 45 to below 75; hard at 75+ | Broad bands make the policy interpretable and avoid pretending scores warrant fine-grained difficulty estimation. |
| Low evidence | Score below 60 | A simple threshold for identifying work needing review, not an institutional passing grade. |
| Repeated mistake | At least 3 scores below 60 in the latest 10 | Require a pattern rather than one slip; the bounded window lets older failures age out by attempts. They need not be consecutive. |
| Growth | Delta at least +3 → improving; otherwise delta at most −3 or current score below 60 → needs_attention; otherwise stable | Ignore small fluctuations while flagging low performance. Branch order means a low score rising by 3+ is still “improving.” |
| Recommendation precedence | Repeated mistake, then low mastery, then improving | Name recurring difficulty first instead of burying it under a generic practice suggestion. |
| Recommendation count | First 3 generated items | Keep the next-action list manageable; this is truncation, not a globally ranked optimal list. |

The recommendation helper computes growth from its two latest assessment scores, not a stored long-term EMA trend. Policies do not model item difficulty statistically, deduplicate question exposure comprehensively, or implement spaced repetition.

## 7. Confidence calibration — a second, self-reported signal

The PRD asks the system to “identify weaknesses” and recommend the next action, but every signal it names measures *produced* knowledge — what a learner can answer when asked. A learner who rates themselves certain and scores 46% will not study, because they believe the material is already known. That gap is invisible to a score-only model, so the assessment flow asks for a one-tap confidence rating **before** the answer is graded.

**Design decisions:**

- A 5-point self-report (Guess / Not sure / Fairly sure / Confident / Certain) maps to a 0–100 prediction (20/40/60/80/100), making it directly comparable with the graded `overall_score`. Five options is a deliberate ceiling: the prediction has to cost the learner almost nothing or it will be skipped.
- Bias = mean(predicted) − mean(actual). Above **+12** is `overconfident`, below **−12** is `underconfident`, otherwise `well_calibrated` (constants in `app/config.py`). `mean_absolute_error` reports the size of the miss regardless of direction.
- **The arithmetic is deterministic and never model-judged.** The LLM grades the answer; it does not get to assess a learner's self-awareness, for the same reason mastery is not model-judged: it must be auditable and must not flatter.
- An overconfidence gap outranks `low_mastery` in the recommendation priority, because the learner is not motivated to review something they believe they know. The remedy it suggests is retrieval practice (closed-book re-test), not re-reading.
- Prediction is optional at the API level and, on the client, required to submit — a graded answer with no prediction is still valid evidence, it simply carries no calibration signal, and such rows are excluded from the arithmetic rather than being counted as perfect foresight.

**Boundary:** `predicted_score` was added as a nullable column via additive `ALTER TABLE`, so answers recorded before this feature keep their result and simply have no prediction.

## 8. Groq model substitution

The pre-existing assumptions note records that the previously used Groq Llama-3.x identifiers were removed from the account's available catalog during the build window. It records `openai/gpt-oss-120b` as the selected available tool-calling replacement.

**Reasoning:** Preserve the existing `ChatGroq`/LangGraph integration and required generation capability rather than redesigning the provider layer under time pressure. Availability and compatibility drove substitution; no independent “best model” benchmark is claimed.

`GROQ_MODEL` is required. `GROQ_QUIZ_MODEL` falls back to it, but `GROQ_QUIZ_API_KEY` remains required separately. The chat client sets temperature 0 to reduce tool-routing variability; the quiz client does not explicitly set temperature, so identical generation behavior is not promised. Provider catalogs and quotas can change again.

## 9. NVIDIA/cloud embeddings replaced by local sentence-transformers

**Current decision:** Use `HuggingFaceEmbeddings` with `BAAI/bge-small-en-v1.5` locally, with local `BAAI/bge-reranker-base` reranking. No NVIDIA/NIM credential is required.

**Reasoning:** Remove cloud embedding credentials, per-request embedding quota, and network availability from ingestion/retrieval while preserving the existing FAISS interface. This simplifies fresh-clone setup and keeps embedding inference local.

**Evidence boundary:** Earlier NVIDIA/NIM terminology remains in code/document history, but the available sources do not establish a specific NVIDIA outage, error code, or removal date. No such incident is invented here.

**Tradeoffs:** First-use model downloads still need internet; CPU/RAM usage and cold-start latency move to the host. Local embeddings do not make the whole product offline: selected context is still sent to Groq. Indexes created with a different embedding model must be rebuilt rather than assumed compatible.

## 10. Retrieval fusion and bounded context

The retriever defaults to dense weight 0.6, BM25 weight 0.4, and RRF constant 60 when hybrid mode is selected.

**Reasoning:** Give semantic matching a slight preference while retaining exact terminology; rank-based fusion avoids directly mixing incompatible raw dense and lexical scores. The RRF constant dampens dominance by the top rank. These are starting settings, not demonstrated optima.

Default retrieval keeps a small final evidence set (`k=6`, rerank top 4; callers can override) to bound context and generation cost. This can omit needed multi-page evidence. Caching avoids repeated local work but is process-local, not distributed infrastructure.

## 11. SQLite instead of Postgres

**Decision:** Keep SQLite, WAL, and SQLAlchemy for this prototype.

**Reasoning:** Zero database-service provisioning and compatibility with the inherited application/checkpointer favor reliable local demonstration over a rushed migration. The compact brief explicitly permits SQLite as a scoped tradeoff.

**Consequence:** Limited concurrent writes and horizontal scaling; local files need persistence and backups. A `DATABASE_URL` variable alone does not establish tested Postgres support. Lightweight startup schema changes are not a full migration strategy.

## 12. Text PDFs, not OCR or multimodal document understanding

**Decision:** Extract PDF text and preserve source/page and table-like structure where possible; omit OCR.

**Reasoning:** Prioritize traceable retrieval and refusal before adding OCR dependencies, layout models, and uncertain recognition quality. The brief explicitly allows documenting OCR as a limitation.

**Consequence:** Scanned/image-only pages and diagrams may not be understood. Text/caption retrieval is not visual reasoning, and structure-aware chunking does not guarantee accurate table reconstruction.

## 13. Events and internal mutations

**Decision:** Separate general learning events from AI telemetry, deduplicate by stable event key, and keep mastery mutation internal. Recommendations exposed to the agent are read-only.

**Reasoning:** Separate product activity from provider diagnostics and reduce the chance of duplicate learning evidence or model-directed arbitrary state changes.

**Boundary:** This differs from the compact brief's requested model-facing mutation-tool pattern. Event-key checks and separate commits are not an exactly-once distributed transaction guarantee. New random keys represent new events and cannot identify semantic duplicates automatically.

## 14. Ingestion jobs and prototype observability

The upload route currently ingests inline and records successful job state afterward; retry changes failed state back to queued.

**Reasoning for retaining this in this documentation phase:** the build is documentation-only, so existing request compatibility is described rather than replaced with a worker. This is a limitation against the PRD's asynchronous/recovery requirements, not an assertion that inline work satisfies them.

Likewise, available AI log fields and optional LangSmith traces are useful diagnostics, but placeholder/missing metrics must not be presented as measured latency, token use, or cost.

## 15. Admin role = oversight interface, not the student learning UI

**Decision:** Admin-role accounts never see the student application (Spaces/Projects onboarding, learning sidebar, Tutor/Quiz/Flashcards/Progress/Study Plan). On sign-in they land directly in a dedicated Admin Console whose only navigation is oversight: Users, Spaces, Projects, Activity, AI Usage, AI Evaluation, Background Jobs, and System Health.

Inspecting one user's learning journey (PRD §16: Projects, activity, assessments, progress, AI usage) happens inside the console as a **read-only inspector panel** over that user's data. The admin is never given their own live Tutor/Quiz/Flashcard session — the console shows the learner's records; it does not act as the learner.

**Reasoning:** The PRD frames admin purely as an inspection/oversight role (§16 uses only "inspect/view/filter" verbs, never "create" or "practise"), so admin capabilities are modelled as verbs over other users' data. A platform admin using the AI Tutor as a personal chatbot does not align with the role's actual purpose, and exposing student workspaces to admins would also widen the surface for accidental cross-account actions. Admins who want the learner experience create a separate student account. Separation also keeps the student shell free of role-conditional UI: the sidebar registry is student-only by construction rather than filtered by `role` at render time.

**Boundary:** The PRD doesn't specify whether admins need their own Spaces/Projects; assumed no, since §16 frames the admin role as platform oversight, not as a learner. Promotion of additional admins remains a direct DB update — there is deliberately no in-product path that grants the admin role.

## 16. Evaluation and submission evidence

- The owner confirmed P4 and 193/193 backend tests; this documentation pass accepts that handoff without rerunning.
- Saved `backend/eval/results.md` records **6/8**, not 8/8. Backend test success and live model quality measure different things.
- Node-version problems blocking `npm run build` remain documented; `npm run dev` is reported working. No package or runtime changes are authorized in this pass.
- Fresh-clone commands are source-checked instructions, not a claim of executed installation.
- Public deployment, repository visibility, and the PRD §20 demo video require separate evidence; none is invented from the presence of a remote URL.
- The prompt log preserves available actual prompts and identifies missing historical transcripts rather than fabricating a complete development history.
