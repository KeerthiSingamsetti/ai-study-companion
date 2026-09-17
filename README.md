# AI Study Companion — StudyMate Extension

A PDF-grounded study workspace built with FastAPI, LangGraph, React 19, and Vite. Students organize materials into Spaces and Projects, ask questions with source references, practice quizzes and flashcards, and inspect learning progress and analytics.

**Provenance:** The RAG/agent core is inherited from the prior team project **StudyMate**. This submission substantially extends it with authenticated ownership, project organization and isolation, stronger grounding, learning-loop services, and observability/dashboard surfaces. See [AI_USAGE.md](AI_USAGE.md) for inherited versus new components.

## Status and documentation

- P4 completion and **193/193 passing backend tests** were confirmed by the project owner at handoff; tests were not rerun during this documentation-only phase.
- The saved live evaluation artifact currently records **6/8 passed**, a different measure from the backend test suite. See [EVAL_WRITEUP.md](EVAL_WRITEUP.md).
- `npm run dev` is reported working. `npm run build` is blocked by a Node-version issue in the development environment; a production build is not claimed.

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Runtime components, data flow, persistence, and boundaries |
| [AI_USAGE.md](AI_USAGE.md) | Product AI, development AI, and reuse disclosure |
| [EVAL_WRITEUP.md](EVAL_WRITEUP.md) | Tests, saved evaluation, and measurement limits |
| [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) | Operational and functional constraints |
| [ASSUMPTIONS.md](ASSUMPTIONS.md) | Formulas, thresholds, substitutions, and tradeoffs |
| [DEV_PROMPTS_LOG.md](DEV_PROMPTS_LOG.md) | Available development prompt record |

## Prerequisites

- Git and Python **3.12** recommended.
- A current Node.js release compatible with the installed Vite 8 toolchain; use **Node 22.12+ on the 22.x line** rather than the old README's Node 18 recommendation. Check `node --version` and package-engine warnings.
- Groq API access to `openai/gpt-oss-120b` (or another explicitly configured compatible model).
- Internet access for dependency installation and the first download of local Hugging Face models. Embedding and reranking inference then run locally; tutoring/generation still use Groq.
- Writable local storage for SQLite databases and vector indexes.

## Fresh-clone setup

The commands below start from a directory where you want the clone. Keep the backend and frontend in separate terminals.

### 1. Clone and install backend dependencies

```sh
git clone https://github.com/KeerthiSingamsetti/ai-study-companion.git
cd ai-study-companion/backend
python -m venv .venv
```

Activate the virtual environment:

**Windows Command Prompt**
```bat
.venv\Scripts\activate
```

**macOS/Linux**
```sh
source .venv/bin/activate
```

Then install:

```sh
pip install -r requirements.txt
```

### 2. Configure `backend/.env`

Create `.env` in `backend/` with the following content, replacing the placeholders:

```dotenv
GROQ_API_KEY=replace_with_your_groq_key
GROQ_MODEL=openai/gpt-oss-120b
GROQ_QUIZ_API_KEY=replace_with_your_groq_key
GROQ_QUIZ_MODEL=openai/gpt-oss-120b
SECRET_KEY=replace_with_a_long_random_secret

LANGSMITH_TRACING=false
LANGCHAIN_TRACING_V2=false
```

Both API-key variables are required by application startup. The same Groq key can be assigned to both; separate keys are optional, not a requirement for two accounts. `GROQ_QUIZ_MODEL` falls back to `GROQ_MODEL` if omitted, but the quiz API key has no corresponding fallback.

Generate a signing secret locally if needed:

```sh
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not commit `.env` or paste real credentials into documentation. The existing `.env.example` contains only part of the required configuration and enables tracing: copying it without adding the model, quiz key, and signing secret is insufficient.

Optional configuration:

| Variable | Behavior |
|---|---|
| `DATABASE_URL` | Omit to use the absolute default path `backend/chatbot.db`. If running from `backend/`, `sqlite:///chatbot.db` is a relative alternative. Do not use `sqlite:///backend/chatbot.db` from that directory. |
| `RERANKER_MODEL` | Defaults to local `BAAI/bge-reranker-base`. Changing it may require relevance-threshold revalidation. |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT` | Optional tracing; enable only with valid credentials and consent to send trace content. Standard endpoint: `https://api.smith.langchain.com`. |

The embedding provider is local `sentence-transformers` through `HuggingFaceEmbeddings`, using `BAAI/bge-small-en-v1.5`. **No NVIDIA API key or cloud embedding endpoint is required.** Application initialization loads `backend/.env` with override enabled, so its values take precedence over conflicting process values.

### 3. Start the backend

With the virtual environment active, from `backend/`:

```sh
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Startup initializes application tables and a separate LangGraph checkpoint database. Initial model downloads/loading may delay readiness.

API documentation: <http://127.0.0.1:8000/docs>.

### 4. Install and start the frontend

In a second terminal, from the clone root:

```sh
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally <http://localhost:5173>). The dev proxy forwards `/api/*` to `http://127.0.0.1:8000/*`, removing `/api`; no separate frontend API-base environment variable is needed for this setup.

**Build caveat:** `npm run dev` works in the reported environment, but `npm run build` is currently blocked by a Node-version issue. Use a compatible Node version and revalidate the build before deployment. This documentation phase did not install packages, run a fresh clone, or claim to resolve the blocker.

## First-use walkthrough

1. Register/sign in through the application; the legacy seeded `default_user` is not a documented login account.
2. Create a Space and Project.
3. Upload a text-based PDF and wait for ingestion readiness before querying it.
4. Ask a question supported by the material and inspect the returned document/page references.
5. Ask a clearly out-of-document question in the grounded tutor flow and inspect the insufficient-evidence response.
6. Generate a quiz or flashcards and review the available progress and dashboard views.
7. Use a separate project/account when manually checking isolation; do not assume a source selector alone enforces access control.

## Project layout

```text
backend/
  app/
    agent/       LangGraph orchestration, prompts, LLM clients, checkpoints
    api/         HTTP routes for chat, documents, projects, study tools, analytics
    auth/        Authentication and authorization dependencies
    db/          SQLAlchemy models, sessions, CRUD, events and usage records
    rag/         PDF extraction, chunking, embeddings, retrieval and reranking
    schemas/     Validated request/result contracts
    services/    Chat, document, grading, mastery and learning policies
    tools/       Model-facing RAG, study-tool and recommendation wrappers
    main.py      Application composition and lifecycle
  tests/         Backend unit and integration/regression tests
  eval/          Evaluation manifests, runners and saved results
frontend/
  src/           React workspace, dashboards, shared state and API clients
  vite.config.js Development server proxy
```

## Testing and evaluation

From `backend/`, with the virtual environment active:

```sh
python -m pytest tests/ -v
```

Tests marked `integration` may require network access/model downloads. To exclude those marked cases:

```sh
python -m pytest tests/ -v -m "not integration"
```

Marker filtering is not an offline sandbox; inspect configuration and use a disposable development database because test fixtures initialize tables and users.

The P4 manifest can be checked without making a model call:

```sh
python eval/p4_eval.py --validate-only
```

To deliberately rerun the live evaluation later:

```sh
python eval/p4_eval.py
```

The latter uses `backend/islr.pdf`, local embeddings/retrieval and Groq generation, may build `backend/vectorstores/p4_islr_live_eval`, and overwrites `backend/eval/results.md`. It requires credentials, can consume provider quota, and was **not** run for P5.

## Scope

SQLite rather than Postgres, no OCR for scanned PDFs, local rather than cloud embeddings, heuristic mastery/recommendation policies, and incomplete production-build validation are deliberate or documented constraints. Read [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) before treating this development setup as production-ready.