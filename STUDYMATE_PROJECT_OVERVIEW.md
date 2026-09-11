# 📚 StudyMate — Complete Project Overview

> **Scope:** Everything built from scratch to the current state — architecture, tech stack, data flow, features, evaluation, state management, and user experience.

---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Introduction](#2-introduction)
3. [Related Works / Existing Works](#3-related-works--existing-works)
4. [Proposed Method](#4-proposed-method)
5. [User Interface & Design System](#5-user-interface--design-system)
6. [State Architecture & Data Flow](#6-state-architecture--data-flow)
7. [Experimental Setup & Evaluation](#7-experimental-setup--evaluation)
8. [Conclusions](#8-conclusions)
9. [Future Scope / Directions](#9-future-scope--directions)
10. [References](#10-references)

---

## 1. Abstract

**StudyMate** is an AI-powered, document-grounded study assistant built as a full-stack web application. Students upload academic course PDFs; the system automatically chunks, embeds, and indexes them into a hybrid vector/keyword database, exposing an intelligent chat interface and specialized study workspaces:

- **Document Q&A**: Answers questions grounded directly in uploaded PDFs with source filename and page-level citations.
- **Quiz Workspace**: Auto-generates 4-option multiple-choice practice quizzes with answer rationale and RAG page evidence, complete with Framer Motion option animations (green check / red shake).
- **Flashcards Workspace**: Fixed-width 3D card flip with anti-aliased font rendering, XP counters, study streaks, circular SVG progress tracking, and canvas-confetti deck completion celebrations.
- **Study Plan Workspace**: Builds structured day-by-day revision schedules with interactive task checklists and percentage progress tracks.
- **Study Progress & "Quiz Me on This" Flow**: Tracks weak topics across sessions and enables single-click contextual quiz creation pre-filled with weak topic metadata and source PDFs.

The backend is built on **FastAPI + LangGraph**, LLM inference runs on **Groq Cloud** (`llama-3.3-70b-versatile`), embeddings use **NVIDIA NIM** (`nv-embedqa-e5-v5`), and the frontend is a **React 19 + Vite + Framer Motion** single-page application. State management uses `WorkspaceContext.jsx` as a single source of truth, and data is persisted in **SQLite** (WAL mode).

![StudyMate Demo](studymate.gif)

---

## 2. Introduction

### i. Motivation for the Work

Students reading dense academic PDFs often lack a personalized AI study companion capable of:
- Answering subject questions grounded strictly in their course text
- Auto-generating practice quizzes with verifiable page citations
- Providing interactive, spaced-repetition flashcards
- Automatically identifying weak topics and allowing instant revision

Generic chatbots often hallucinate and lack context persistence. StudyMate solves this by combining **Hybrid Retrieval-Augmented Generation (RAG)** with a **deterministic intent router** and a **persistent memory layer**.

### ii. Real-world Applications

| Domain | Use Case |
|---|---|
| Higher Education | Students upload lecture notes and ask topic questions before exams |
| Competitive Exams | GRE / UPSC prep — upload study material, auto-generate topic quizzes |
| Corporate L&D | Employees upload training manuals, study via 3D flashcards |
| Self-Paced Learning | Learners track weak topics across sessions and launch 1-click review quizzes |

---

## 3. Related Works / Existing Works

### i. Limitations of Existing Tools

| System | Feature Scope | Limitation |
|---|---|---|
| **ChatPDF** | Question answering over PDFs | No quiz generation, flashcards, or progress memory |
| **Quizlet** | Flashcards & quizzes | Manual deck creation; not grounded in user PDFs |
| **Khanmigo** | AI tutoring | Closed corpus; cannot ingest arbitrary user documents |
| **Perplexity AI** | Web search assistant | No local PDF indexing; no personalized weak-topic memory |

### ii. Research & System Gaps Solved by StudyMate

1. **Deterministic Intent Routing**: Classifies queries via pure-Python regex before binding LLMs, avoiding function-calling overhead and errors.
2. **Contextual Single-Click Workflows**: Seamlessly bridges progress tracking with quiz generation by carrying over weak topics, source document IDs, and configuration in a single click.
3. **Hybrid RAG Retrieval**: Merges FAISS dense vector search, BM25 keyword matching, and Cross-Encoder reranking for optimal recall precision.
4. **Single Source of Truth State**: Eliminates state fragmentation between App shells and workspace routers.

---

## 4. Proposed Method

### System Architecture Diagram

```
+---------------------------------------------------------------+
|                        USER  (Browser)                        |
|  React 19 SPA (Vite + Framer Motion)                          |
|  TopBar Header | Floating Sidebar | Workspace Router          |
|  Workspaces: Chat | Documents | Flashcards | Quiz | Planner | Prog|
+------------------------------+--------------------------------+
                               | REST / SSE  (HTTP)
                               v
+---------------------------------------------------------------+
|                   FastAPI  Backend  (Python)                   |
|                                                               |
|  POST /chat/{thread_id}/message  ──────────────+             |
|  POST /documents/{thread_id}/upload            |             |
|  GET  /threads / /progress / /quiz / /planner  |             |
|                                                |             |
|          +─────────────────────────────────────+             |
|          v                                                    |
|   +--------------+                                           |
|   | Intent Router| <- pure Python regex, zero LLM cost       |
|   |  (no LLM)    |                                           |
|   +------+-------+                                           |
|          |  classify_intent()                                 |
|          v                                                    |
|  +-------------------------------------------------------+   |
|  |          LangGraph  StateGraph  (intent-routed)        |   |
|  |  START -> intent_router                                |   |
|  |    +----> general_chat / doc_qa / quiz / flashcard     |   |
|  |            study_plan / progress / no_document         |   |
|  |    +----> ToolNode -> synthesis -> END                 |   |
|  +-------------------------------------------------------+   |
|                                                               |
|  +-----------------------------------------------------------+ |
|  |                    Hybrid RAG Pipeline                     | |
|  |  PDF Upload -> PyPDF -> Chunker -> FAISS VectorStore       | |
|  |  Query -> BM25 + FAISS -> RRF Merge -> Cross-Encoder     | |
|  +-----------------------------------------------------------+ |
|                                                               |
|  +-----------------------------------------------------------+ |
|  |                   Persistence Layer                        | |
|  |  SQLite (chatbot.db) via SQLAlchemy ORM (WAL Mode)        | |
|  |  LangGraph Checkpointer (langgraph_checkpoints.db)        | |
|  +-----------------------------------------------------------+ |
+---------------------------------------------------------------+
```

---

## 5. User Interface & Design System

The StudyMate frontend follows modern product design aesthetics (inspired by Linear, Perplexity, Raycast, and Notion):

- **Canvas Background**: Deep dark theme (`#09090F`) with subtle radial gradients.
- **Glassmorphic Floating Sidebar**: Floating glass panel featuring Framer Motion `layoutId="activeWorkspacePill"` smooth highlight pills.
- **Flashcards Workspace**: Fixed-width centered cards (`max-w-md`) with 3D flip animation, anti-aliased font smoothing (`-webkit-font-smoothing: antialiased; transform: translateZ(0)`), circular SVG progress ring, study streak tracking, and canvas-confetti deck completion.
- **Quiz Workspace**: Floating question cards, green checkmark animation for correct choices, red shake animation (`x: [-10, 10, -8, 8, 0]`) for wrong choices, and expanded RAG citation page tags.
- **Weak Topic Banner**: Contextual setup banner automatically pre-filled when clicking *"Quiz Me on This"* in Study Progress.

---

## 6. State Architecture & Data Flow

To prevent data loss and UI sync issues during workspace navigation, state management is centralized in `WorkspaceContext.jsx`:

1. **Sole State Authority**: `WorkspaceContext.jsx` manages `activeWorkspace`, `activeThreadId`, `quizPrefill`, `flashcardPrefill`, `quizData`, `flashcardData`, `planData`, and `progressData`.
2. **Context Merging**: External props passed to `<WorkspaceProvider value={...}>` are merged at the top (`...(value || {})`), preventing stale shell state from overwriting active prefill payloads.
3. **Single-Click Navigation (`handleUsePlanTopic`)**:
   ```javascript
   const handleUsePlanTopic = useCallback((targetWorkspace, topic, docId, options = {}) => {
     if (targetWorkspace === 'quiz') {
       setQuizData(null) // Resets previous quiz state to show weak topic banner
       setQuizPrefill({
         documentId: docId || options.documentId || '',
         documentName: options.documentName || '',
         topic: topic || '',
         difficulty: options.difficulty || 'medium',
         numQuestions: options.numQuestions || 10,
         quizMode: options.quizMode || 'topic',
         source: options.source || 'study-progress',
       })
       setActiveWorkspace('quiz')
     }
   }, [])
   ```

---

## 7. Experimental Setup & Evaluation

The backend test suite verifies intent routing, retrieval grounding, user memory persistence, and tool output schema validation.

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/ -v
```

### Test Results Summary

| Test Module | Coverage | Status |
|---|---|---|
| `test_intent_router.py` | Intent classification & short-circuits | 100% PASSED |
| `test_progress_memory.py` | Weak topic tracking & attempt logging | 100% PASSED |
| `test_quiz_generator.py` | Quiz tool output & RAG generation | 100% PASSED |
| `test_rag_pipeline.py` | Ingestion, FAISS/BM25 indexing & reranking | 100% PASSED |
| `test_rag_query_citations.py` | Page citation extraction & deduping | 100% PASSED |
| `test_user_memory.py` | Thread-scoped user context formatting | 100% PASSED |
| **Total Test Suite** | **161 Integration Tests** | **161 PASSED (100%)** |

---

## 8. Conclusions

StudyMate provides an end-to-end contextual learning workspace combining modern frontend aesthetics, robust state management, deterministic agent routing, hybrid RAG retrieval, and verifiable page citations. The single-click *"Quiz Me on This"* workflow seamlessly connects student progress metrics to actionable study practice.

---

## 9. Future Scope / Directions

- Support multi-modal PDF processing (OCR for scanned diagrams and handwritten notes).
- Implement spaced-repetition scheduling algorithm (SuperMemo SM-2) for flashcards.
- Introduce collaborative group study workspaces with shared document indices.

---

## 10. References

1. LangGraph Documentation: https://langchain-ai.github.io/langgraph/
2. FastAPI Framework: https://fastapi.tiangolo.com/
3. FAISS Vector Search: https://github.com/facebookresearch/faiss
4. Framer Motion API: https://www.framer.com/motion/
