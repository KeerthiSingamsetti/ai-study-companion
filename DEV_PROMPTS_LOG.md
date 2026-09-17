# Development Prompts Log

## Scope and provenance

[Project_Requirements.pdf](Project_Requirements.pdf) §20 requests actual prompts materially used with development AI tools. This log records the available prompt sources, not a reconstructed fictional transcript.

- The existing [antigravity_prompt_compact.md](antigravity_prompt_compact.md) is the preserved build brief and is incorporated by reference in full.
- The current session supplies the actual P5 request and reference clarification quoted below.
- Earlier per-phase conversations, timestamps, model choices, debugging exchanges and complete assistant outputs were not available in the inspected record. They are not invented.
- Requirements are taken from the actual PDF, not the compact brief's unfilled `[PRD]` placeholder.
- Product runtime prompts are separate from development prompts; examples live in `backend/app/agent/prompts.py`, `backend/app/services/rag_query_service.py` and `backend/app/services/grading.py`.

## 1. Architecture and phased implementation brief

**Source:** [antigravity_prompt_compact.md](antigravity_prompt_compact.md).  
**Record type:** Actual repository prompt; original execution dates and full historical responses unavailable.

Selected verbatim excerpts (the linked file retains the complete prompt):

> Extend, do not rewrite. StudyMate's RAG/agent core is proven and tested — reuse it.

> Postgres if time allows; else keep SQLite, note as scoped tradeoff

> Concept mastery %: recency-weighted score from quiz/assessment evidence (pick + document a formula)

> Small eval harness: 8-10 cases incl. grounded+cited answer, correct refusal, injection resistance → pass/fail table in repo

> State plainly: RAG/agent core is from a prior team project (StudyMate) where I was primary owner of retrieval/agent architecture. This submission extends it. List inherited vs new.

### Organization of the preserved brief

The following is an index/summary, not additional verbatim prompts:

| Category | Location in the original brief | Requested work |
|---|---|---|
| Architecture | Constraint, existing stack, build order | Reuse StudyMate; retain layered RAG/agent architecture |
| Backend/database | P1 Foundation | Authentication, user scoping, Spaces/Projects and project-index isolation |
| AI/retrieval | P2 Grounding | Provenance, citations, relevance refusal, untrusted document handling and structure-aware chunking |
| Learning/assessment | P3 Learning loop | Mastery formula, structured open-ended grading, adaptation, growth and repeated mistakes |
| Observability/background | P4 Observability + surfaces | Separate AI/general events, idempotency, ingestion states and admin visibility |
| Frontend | P4 dashboard requirements | Home, project and learner analytics surfaces |
| Testing | P1/P2 tests, P4 evaluation, final check | Isolation, refusal, injection and real evaluation evidence |
| Documentation | P5 Submission, transparency | Setup, architecture, AI reuse disclosure, assumptions, limitations and prompt log |

The brief is evidence of requested scope, not proof that every requested feature was implemented or verified. Differences found in source are documented in `ARCHITECTURE.md` and `KNOWN_LIMITATIONS.md`.

## 2. P5 documentation request

**Source:** Project-owner message in this session, 2026-09-17.  
**Category:** Documentation and submission.  
**Record type:** Actual prompt, reproduced below.

```text
ignore that prompt,,,see this,,P4 confirmed 100% done, 193/193 tests passing.

Proceed to P5: README.md (fresh-clone setup: git clone → pip install
-r requirements.txt → .env setup → uvicorn → npm install → npm run dev),
ARCHITECTURE.md, AI_USAGE.md (explicitly state RAG/agent core inherited
from prior team project StudyMate, this submission substantially extends
it — list inherited vs new components), EVAL_WRITEUP.md,
KNOWN_LIMITATIONS.md (SQLite not Postgres, no OCR for scanned PDFs,
local embeddings via sentence-transformers not cloud API, Node version
issue blocking npm run build — npm run dev works fine), ASSUMPTIONS.md
(specific reasoning for every judgment call: mastery EMA formula and
weights, 0.35 relevance threshold, 0.88 concept-resolution threshold,
Groq/NVIDIA provider substitutions and why), DEV_PROMPTS_LOG.md.

No new code, no API calls needed — pure documentation. Report format
only: files created, deviations if any.
```

**Work performed:** Source and requirements inspection; drafting the seven requested Markdown documents; local static documentation checks. No application code, threshold, test assertion or saved evaluation result was changed.

**Evidence handling:** The 193/193 backend result is attributed to the owner's handoff. The saved live evaluation separately says 6/8; documentation preserves that distinction rather than inventing an 8/8 result.

## 3. Reference clarification

**Source:** Project-owner feedback during the README write, 2026-09-17.  
**Category:** Requirements/documentation.  
**Record type:** Actual prompt.

```text
for refernce use  antigravity-prmpt compact.md and project reqirements pdf ok,
```

**Action:** Used the repository files `antigravity_prompt_compact.md` and `Project_Requirements.pdf`. Read the actual PRD, including submission, evaluation and full learning-loop requirements.

## Record limitations

There is no complete prompt-by-prompt evidence for the earlier implementation phases in this log. The preserved build brief and current messages are the available actual sources. Claims of a particular assistant having written every feature, exhaustive human review, a newly executed fresh-clone installation, or newly passing tests would exceed that evidence.