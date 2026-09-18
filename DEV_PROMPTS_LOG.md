# Development Prompts Log

## Scope and provenance

[Project_Requirements.pdf](Project_Requirements.pdf) §20 asks for the actual prompts I materially used with development AI tools. This log records the prompt sources I actually have. It is not a reconstructed transcript.

- The existing [compact_prompt.md](compact_prompt.md) is the build brief I kept, and it is incorporated by reference in full.
- The current session gives me the actual P5 request and the reference clarification quoted below.
- I don't have my earlier per-phase conversations, timestamps, model choices, debugging exchanges or full assistant outputs, so I have not made any of them up.
- Requirements come from the actual PDF, not from the compact prompt's unfilled `[PRD]` placeholder.
- Product runtime prompts are separate from development prompts. Examples live in `backend/app/agent/prompts.py`, `backend/app/services/rag_query_service.py` and `backend/app/services/grading.py`.

## 1. Architecture and phased implementation brief

**Source:** [compact_prompt.md](compact_prompt.md).  
**Record type:** Actual repository prompt. The original execution dates and full historical responses are not available.

Selected verbatim excerpts (the linked file has the complete prompt):

> Extend, do not rewrite. StudyMate's RAG/agent core is proven and tested — reuse it.

> Postgres if time allows; else keep SQLite, note as scoped tradeoff

> Concept mastery %: recency-weighted score from quiz/assessment evidence (pick + document a formula)

> Small eval harness: 8-10 cases incl. grounded+cited answer, correct refusal, injection resistance → pass/fail table in repo

> State plainly: RAG/agent core is from a prior team project (StudyMate) where I was primary owner of retrieval/agent architecture. This submission extends it. List inherited vs new.

### Organization of the preserved brief

The table below is an index and summary, not additional verbatim prompts:

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

The brief shows what I asked for, not proof that every requested feature was implemented or verified. Differences I found in the source are documented in `ARCHITECTURE.md` and `KNOWN_LIMITATIONS.md`.

## 2. P5 documentation request

**Source:** cline  
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

**Work performed:** I inspected the source and requirements, drafted the seven requested Markdown documents and ran local static documentation checks. I did not change any application code, threshold, test assertion or saved evaluation result.

**Evidence handling:** The 193/193 backend result comes from my own P4 handoff. The saved live evaluation separately says 6/8. The documentation keeps that distinction and does not claim an 8/8 result.

## 3. Reference clarification

**Source:** Cline 
**Category:** Requirements/documentation.  
**Record type:** Actual prompt.

```text
for refernce use  antigravity-prmpt compact.md and project reqirements pdf ok,
```

**Action:** Used the repository's compact prompt file and `Project_Requirements.pdf`. Read the actual PRD, including the submission, evaluation and full learning-loop requirements.

## Record limitations

I don't have complete prompt-by-prompt evidence for the earlier implementation phases. The preserved build brief and my messages from this session are the actual sources I have. Any claim that a particular assistant wrote every feature, that I reviewed everything exhaustively, that I ran a new fresh-clone installation, or that tests newly passed would go beyond that evidence.