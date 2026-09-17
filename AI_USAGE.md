# AI Usage and Project Provenance

References: [Project_Requirements.pdf](Project_Requirements.pdf), §20, and [antigravity_prompt_compact.md](antigravity_prompt_compact.md).

## Prior team project disclosure

**The RAG/agent core is inherited from the prior team project StudyMate. This submission substantially extends it; it is not a from-scratch implementation of the entire system.**

The project owner's contribution statement in the compact brief says they were the **primary owner of retrieval/agent architecture** in that prior team project. This records the owner's attribution; it does not claim sole authorship of the team project.

### Inherited versus new/extended components

The division below follows the baseline and phase descriptions in the compact brief, checked against repository components. It is a component-level disclosure, not a line-by-line authorship audit.

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

An extension listed here may be a service or contract rather than a complete browser workflow. In particular, job states do not constitute a durable background worker, and standalone learning-policy tests do not establish end-to-end assessment integration. See [ARCHITECTURE.md](ARCHITECTURE.md).

## AI used to build the product

AI development assistance was organized through the repository's compact build prompt covering architecture, backend/database, grounding, learning policies, frontend surfaces, debugging/testing and submission documentation.

For this P5 session, Cline was used in Antigravity IDE to:
- Read the requirements PDF, compact prompt, configuration, relevant implementation and saved evaluation.
- Draft and revise the seven requested Markdown documents.
- Check documentation consistency locally.

This session is documentation-only: no application code changes, product-model/API calls, package installation, live evaluation or backend test rerun are part of P5.

The available context does not contain a complete historical assistant-session export, all earlier model identities, or a per-file AI-authorship ledger. Those details are not invented. [DEV_PROMPTS_LOG.md](DEV_PROMPTS_LOG.md) preserves available actual prompts and identifies that evidence boundary.

Development assistance is separate from product behavior: using a coding assistant does not mean that assistant is the model serving the application's tutor.

## AI used by the product

| Capability | Mechanism | External dependency and validation |
|---|---|---|
| Tutor and synthesis | Groq through `ChatGroq`; documented model `openai/gpt-oss-120b` | Model selected by environment; grounded prompts, retrieved evidence and citation parsing |
| Quiz, flashcard and study-plan generation | Dedicated Groq client constructed by `create_quiz_llm` | Configured quiz key/model; study-tool request/output contracts |
| Open-ended grading service | Injected LLM grades against retrieved evidence and rubric | `OpenEndedGrade` validates bounded understanding/accuracy, concept lists and feedback |
| Embeddings | `HuggingFaceEmbeddings`, `BAAI/bge-small-en-v1.5` | Local sentence-transformers inference; first-use model download |
| Reranking | `CrossEncoder`, default `BAAI/bge-reranker-base` | Local inference; configurable model |
| Concept resolution | Exact normalized match, then embedding cosine similarity | Project-local candidates; threshold 0.88 |
| Mastery, adaptation and growth | Deterministic Python policies | No LLM required for the policy calculation |
| Recommendation tool | Rules over persisted mastery and recent assessments | Read-only query; does not require an extra generative model call |
| P4 evaluation | Local retrieval plus Groq answers; keyword/source/refusal checks | Live calls only when deliberately running the evaluator |
| Tracing | Optional LangSmith | Observability service, not a tutor or grading model |

The P4 evaluation's “recommendation” case asks the tutor for a recommendation; it does **not** exercise the deterministic recommendation tool. Likewise, its assessment-category cases are tutor questions, not direct grading-service tests.

Other evaluation utilities/dependencies exist in the repository. Their presence does not establish a measured RAGAS score or a product-time evaluation workflow; the P4 writeup is limited to its saved artifact.

## Data handling and AI boundaries

- Uploaded PDF text, selected evidence, user questions and relevant conversation context may be sent to Groq for generation.
- Local embeddings do **not** mean the whole product is offline or that document content never leaves the host.
- Enabling LangSmith may send prompts, responses and execution context to the tracing service. Tracing is disabled in the README's minimal setup.
- The application stores databases and vector indexes locally. Credentials belong in `.env`, not source, logs or documentation.
- Model output is not authorization. Ownership must come from authenticated server context.
- Document text is untrusted evidence, not permission to execute actions. Prompt-based defenses and limited injection tests do not guarantee immunity.
- Structured-output validation checks shape and bounds, not factual correctness.
- A source reference is useful for inspection but is not itself proof that every sentence is supported.

## Human accountability and results

The project owner remains responsible for submission accuracy, attribution, engineering choices and final validation. The owner reported **193/193 backend tests passing** at P4 handoff. The inspected saved live evaluation separately records **6/8 passed**. Neither was rerun during P5, and the documents do not turn either figure into a claim of complete product correctness.

Provider substitutions and numerical policy choices are explained in [ASSUMPTIONS.md](ASSUMPTIONS.md); operational and evaluation gaps are explicit in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).