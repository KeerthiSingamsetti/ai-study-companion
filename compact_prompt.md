# BUILD TASK: AI Study Companion — extend existing "StudyMate" codebase

## CONSTRAINT
Extend, do not rewrite. StudyMate's RAG/agent core is proven and tested — reuse it. Full PRD is pasted below in [PRD] — treat it as ground truth over this prompt if they conflict.

## EXISTING STACK (do not replace)
FastAPI + LangGraph (9-node agent, one tool/node) · React 19+Vite+Tailwind · Groq openai/gpt-oss-120b (temp=0) · local BAAI/bge-small-en-v1.5 embeddings · FAISS+BM25+RRF fusion+BGE reranker · SQLite+SQLAlchemy · SSE streaming · Pydantic-validated tools · LangSmith tracing.
Gaps in base: no auth/isolation, SQLite only, MCQ-only quiz, weak-topics list (no mastery %), no Space/Project hierarchy, no admin/analytics UI.

## BUILD ORDER — stop at end of a phase if time runs out, don't leave a phase half-done

**P1 Foundation**
- Auth + per-`user_id` scoping enforced at query layer (not just UI)
- Refactor flat `threads`/`documents` → `User→Space→Project→{Materials,Conversations,Concepts,Mastery,Events}`
- Namespace FAISS+BM25 by `project_id` — cross-project retrieval must be impossible, test it
- Postgres if time allows; else keep SQLite, note as scoped tradeoff

**P2 Grounding**
- Carry `{material_id, page_number}` through chunk→fusion→rerank→synthesis → cite as `Source: <name> — Page <N>`
- Expose top rerank score to synthesis; below threshold → explicit "insufficient evidence" response, not a generated guess. Add a test that triggers it.
- Treat document text as untrusted data in system prompt, never instructions. Test: doc containing a fake "ignore previous instructions" line must be ignored.
- Structure-aware chunking: keep table-like blocks atomic; OCR scanned pages if time allows (else note as limitation)

**P3 Learning loop**
- Concept mastery %: recency-weighted score from quiz/assessment evidence (pick + document a formula)
- Open-ended question type + structured (Pydantic) grading: understanding / accuracy / concepts covered / concepts missing
- Adaptive selection using mastery+mistakes+history (not naive wrong→easy/right→hard)
- Growth classification per concept: improving/stable/needs-attention + rule-based recommendation engine
- Repeated-mistake workflow (separate from above): same concept wrong repeatedly → flag pattern → targeted recommendation naming it
- New capabilities (log event, update mastery, recommend) go through same ToolNode/Pydantic pattern as existing tools — no bypassing it

**P4 Observability + surfaces**
- AI-call log: model/feature/latency/tokens/cost/success — reuse LangSmith
- Separate general Events log: project creation, uploads, tutor turns, quiz attempts, assessments, mastery updates, recommendations — idempotent (unique event key, no dupes on retry)
- Background job states for ingestion: `queued→processing→ready/failed`, basic retry
- Admin dashboard: users, projects, activity, AI usage, job states, health
- User-facing Project Analytics + Global Analytics (separate from admin view)
- Home Dashboard (Continue Learning, recent projects, progress, recommended next action) + Project Dashboard (progress, concepts, recent activity, next step) — build these, the demo depends on them
- Small eval harness: 8-10 cases incl. grounded+cited answer, correct refusal, injection resistance → pass/fail table in repo
- Deploy to public URL before writing docs

**P5 Submission**
- README, architecture doc, AI-usage doc (dev-tool AI vs product AI), dev-prompts log, eval writeup, known limitations, assumptions log (specific reasoning, not boilerplate)
- Demo video: full loop in PRD Section 20 order, deliberately show refusal + isolation working, not just described
- Push public repo, verify fresh-clone setup works

## BAR FOR "DONE WELL" (never trade these for extra features)
Refusal branch demoed live · isolation provably enforced (test it) · eval table is real, not claimed · assumptions are specific · every AI feature uses schema-validated output.

## OUT OF SCOPE — flag before building, don't just add
Non-PDF formats, spaced repetition, voice/video, notifications, collab, vector-DB swap, fancier fusion than RRF+rerank.

## TRANSPARENCY (put in docs)
State plainly: RAG/agent core is from a prior team project (StudyMate) where I was primary owner of retrieval/agent architecture. This submission extends it. List inherited vs new.

## FINAL CHECK
Before P5: re-read [PRD] below top-to-bottom against everything built. List anything required/implied not covered by P1-P4, however small. Bring the gap list to me — don't silently add or drop scope.

---
[PRD]
<PASTE FULL PRD TEXT HERE — do not summarize>
