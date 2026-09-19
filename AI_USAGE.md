# AI Usage and Project Provenance

References: [Project_Requirements.pdf](Project_Requirements.pdf), §20, and [compact_prompt.md](compact_prompt.md).

## Prior  project disclosure

**The RAG/agent core is inherited from a previous  project, StudyMate. This submission substantially extends it; it is not a from-scratch implementation of the whole system.**


### Inherited versus new/extended components

The split below follows the baseline and phase descriptions in the compact prompt, checked against the repository's components. It is a component-level disclosure, not a line-by-line authorship audit.

| Inherited foundation | New or substantially extended for this submission |
|---|---|
| FastAPI application, services and SQLAlchemy persistence | Authenticated user ownership and Space/Project organization |
| LangGraph routing, study tools and conversation checkpoints | Ownership-aware execution context and project-isolation coverage |
| PDF extraction, FAISS/BM25 hybrid retrieval, RRF and local reranking | Grounding cutoff integration, citation/provenance handling and stronger document-instruction boundaries |
| Embedding/retrieval interfaces and local BGE architecture | Current local embedding configuration, provider compatibility and index-rebuild support |
| Groq generation integration | Configurable replacement model and explicit setup requirements |
| MCQ quizzes, flashcards, study plans and weak-topic progress | Open-ended grading schema/service, concept resolution, EMA mastery, adaptive-selection and growth helpers |
| Existing study-tool pattern | Read-only, evidence-based recommendation tool and repeated-mistake policy |
| React workspace, SSE chat and shared state | Home/project/global analytics surfaces and revised navigation |
| LangSmith tracing hooks | General events, AI-call/retrieval records, ingestion job contracts and admin aggregate APIs |
| Existing backend regression suite | Learning-policy/grading/mastery/recommendation tests and eight-case P4 evaluation |

Some of the extensions listed here are services or contracts rather than complete browser workflows. In particular, job states are not a durable background worker, and the standalone learning-policy tests do not show end-to-end assessment integration. See [ARCHITECTURE.md](ARCHITECTURE.md).

## AI used to build the product

I organized AI development assistance around the repository's compact prompt, which covers architecture, backend/database, grounding, learning policies, frontend surfaces, debugging/testing and submission documentation.

For this P5 session, I used Cline in Antigravity IDE to:
- Read the requirements PDF, compact prompt, configuration, relevant implementation and saved evaluation.
- Draft and revise the seven requested Markdown documents.
- Check documentation consistency locally.

This session was documentation-only. I made no application code changes, product-model/API calls, package installations, live evaluations or backend test reruns as part of P5.

I don't have a complete export of my earlier assistant sessions, the identities of every model I used along the way, or a per-file record of AI authorship, so I have not tried to reconstruct them. [DEV_PROMPTS_LOG.md](DEV_PROMPTS_LOG.md) keeps the prompts I actually have and marks where that evidence stops.

Using a coding assistant to build the project is separate from how the product behaves. The assistant I coded with is not the model that serves the application's tutor.

## AI used by the product

| Capability | Mechanism | External dependency and validation |
|---|---|---|
| Tutor and synthesis | Groq through `ChatGroq`; documented model `openai/gpt-oss-120b` | Model selected by environment; grounded prompts, retrieved evidence and citation parsing |
| Quiz, flashcard and study-plan generation | Dedicated Groq client constructed by `create_quiz_llm` | Configured quiz key/model; study-tool request/output contracts |
| Open-ended grading service | Injected LLM grades against retrieved evidence and rubric | `OpenEndedGrade` validates bounded understanding/accuracy, concept lists and feedback |
| Embeddings | Cohere hosted Embed API, `embed-english-v3.0` (1024-dim) by default | Hosted inference, no local model memory, requires `COHERE_API_KEY`; switching models requires FAISS index rebuild (`python scripts/rebuild_vectorstore_embeddings.py`) |
| Reranking | `CrossEncoder`, default `BAAI/bge-reranker-base` | Local inference; configurable model; implemented but disabled by default in production (`RERANKING_ENABLED=false`) because the combined local model stack exceeds the hosting tier's memory limit |
| Concept resolution | Exact normalized match, then embedding cosine similarity | Project-local candidates; threshold 0.88 |
| Mastery, adaptation and growth | Deterministic Python policies | No LLM required for the policy calculation |
| Recommendation tool | Rules over persisted mastery and recent assessments | Read-only query; no extra generative model call needed |
| P4 evaluation | Local retrieval plus Groq answers; keyword/source/refusal checks | Live calls only when I deliberately run the evaluator |
| Tracing | Optional LangSmith | Observability service, not a tutor or grading model |

The "recommendation" case in the P4 evaluation asks the tutor for a recommendation. It does **not** exercise the deterministic recommendation tool. Likewise, its assessment-category cases are tutor questions, not direct tests of the grading service.

The repository contains other evaluation utilities and dependencies, but their presence does not mean I measured a RAGAS score or built a product-time evaluation workflow. The P4 writeup covers only its saved artifact.

## Data handling and AI boundaries

- Uploaded PDF text, selected evidence, user questions and relevant conversation context may be sent to Groq for generation.
- Local embeddings do **not** make the whole product offline, and they do not guarantee that document content never leaves the host.
- Turning on LangSmith may send prompts, responses and execution context to the tracing service. Tracing is disabled in the README's minimal setup.
- The application stores databases and vector indexes locally. Credentials belong in `.env`, not in source, logs or documentation.
- Model output is not authorization. Ownership must come from authenticated server context.
- Document text is untrusted evidence, not permission to execute actions. Prompt-based defenses and my limited injection tests do not guarantee immunity.
- Structured-output validation checks shape and bounds, not factual correctness.
- A source reference is useful for inspection, but it is not proof that every sentence is supported.

## My accountability and results

I am responsible for the accuracy of this submission, the attribution, the engineering choices and the final validation. At P4 handoff I had **193/193 backend tests passing**. The saved live evaluation I inspected separately records **6/8 passed**. I did not rerun either during P5, and neither figure should be read as a claim that the product is fully correct.

Provider substitutions and numerical policy choices are explained in [ASSUMPTIONS.md](ASSUMPTIONS.md). Operational and evaluation gaps are listed in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).