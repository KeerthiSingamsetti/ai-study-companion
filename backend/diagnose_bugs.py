
# coding: utf-8
# diagnose_bugs.py  -  Raw-evidence diagnostics for 3 bugs. No patches.
# Run: .venv\Scripts\python.exe diagnose_bugs.py

import json, os, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")          # force UTF-8 on Windows
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=False)

from langchain_core.embeddings import FakeEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_groq import ChatGroq

SEP = "=" * 70

fake_emb = FakeEmbeddings(size=384)

from app.tools.rag_tool import create_rag_tool
from app.tools.quiz_generator_tool import create_quiz_tool
from app.tools.flashcard_tool import create_flashcard_tool
from app.tools.study_planner_tool import create_study_planner_tool
from app.tools.memory_tool import create_study_progress_tool

llm = ChatGroq(
    model=os.getenv("GROQ_MODEL"),
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)

rag_tool   = create_rag_tool(fake_emb)
quiz_tool  = create_quiz_tool(llm, fake_emb)
flash_tool = create_flashcard_tool(llm, fake_emb)
plan_tool  = create_study_planner_tool(llm)
prog_tool  = create_study_progress_tool()

all_tools = [rag_tool, quiz_tool, flash_tool, plan_tool, prog_tool]

from app.agent.nodes.chatbot import (
    _tools_for_turn, _is_progress_request,
    _messages_for_model, _QUIZ_PATTERNS,
)

# ═════════════════════════════════════════════════════════════════════════════
# BUG 1
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + SEP)
print("BUG 1 -- Intent classifier + raw LLM output for 'what topic am I weak at'")
print(SEP)

query_1 = "what topic am I weak at"
msg_1   = HumanMessage(content=query_1)

is_prog = _is_progress_request(query_1)
print("  _is_progress_request(%r) -> %s" % (query_1, is_prog))
bound_1 = _tools_for_turn(all_tools, msg_1)
print("  _tools_for_turn result   -> %s" % [t.name for t in bound_1])

from app.agent.prompts import CHATBOT_SYSTEM_PROMPT
lm_1 = llm.bind_tools(bound_1) if bound_1 else llm

print("\n  Firing Groq with tools: %s" % [t.name for t in bound_1])
try:
    r1 = lm_1.invoke([SystemMessage(content=CHATBOT_SYSTEM_PROMPT), msg_1])
    print("  RAW content       : %r" % r1.content)
    print("  tool_calls        : %s" % r1.tool_calls)
    print("  additional_kwargs : %s" % r1.additional_kwargs)
    hit = re.search(r"\[insert\b.*?\]", str(r1.content), re.IGNORECASE | re.DOTALL)
    print("  Placeholder found? -> %s%s" % (bool(hit), "  <- BUG" if hit else ""))
except Exception as exc:
    print("  ERROR: %s" % exc)

# ═════════════════════════════════════════════════════════════════════════════
# BUG 2
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + SEP)
print("BUG 2 -- 'which quizzes did I attempt' bleeding + stale ToolMessage")
print(SEP)

query_2 = "which quizzes did I attempt"
msg_2   = HumanMessage(content=query_2)

is_prog_2 = _is_progress_request(query_2)
print("  _is_progress_request(%r) -> %s" % (query_2, is_prog_2))
bound_2 = _tools_for_turn(all_tools, msg_2)
print("  _tools_for_turn result   -> %s" % [t.name for t in bound_2])

quiz_match = any(p.search(query_2) for p in _QUIZ_PATTERNS)
print("  _QUIZ_PATTERNS matches?  -> %s%s" % (
    quiz_match,
    "  <- DOUBLE-BINDING BUG" if quiz_match and is_prog_2 else ""
))

# Simulate stale ToolMessage in conversation history
stale = ToolMessage(
    tool_call_id="fake-id-1",
    name="get_study_progress",
    content=json.dumps({
        "quiz_attempts" : [{"topic": "OOP", "score": "7/10", "date": "2026-07-29"}],
        "weak_topics"   : [{"topic": "Polymorphism"}],
        "studied_topics": [{"topic": "Encapsulation"}],
    }),
)

fake_history = [
    HumanMessage(content="what is my progress"),
    AIMessage(content="", tool_calls=[{"name": "get_study_progress", "args": {}, "id": "fake-id-1", "type": "tool_call"}]),
    stale,
    AIMessage(content="You attempted 1 quiz on OOP."),
    msg_2,
]

filtered = _messages_for_model(fake_history, msg_2)
print("\n  _messages_for_model output:")
for m in filtered:
    print("    type=%-20s content_preview=%r" % (type(m).__name__, str(m.content)[:60]))

surviving = [m for m in filtered if isinstance(m, ToolMessage)]
print("  Stale ToolMessages surviving into next turn: %d" % len(surviving))
for tm in surviving:
    print("    name=%r  content[:80]=%r  <- BUG: stale data bleeds" % (tm.name, str(tm.content)[:80]))

# ═════════════════════════════════════════════════════════════════════════════
# BUG 3
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + SEP)
print("BUG 3 -- Citation scoping: which FAISS index is queried per thread?")
print(SEP)

import sqlalchemy
from app.db.session import SessionLocal

db = SessionLocal()
try:
    rows = db.execute(sqlalchemy.text(
        "SELECT id, thread_id, filename, vectorstore_path FROM documents ORDER BY rowid DESC"
    )).fetchall()
finally:
    db.close()

print("  All documents in DB (%d rows):" % len(rows))
for r in rows:
    print("    file=%-30s  thread=%s" % (r[2], r[1]))
    print("    vectorstore_path=%r" % r[3])

from app.tools.rag_tool import get_vectorstore_paths_for_thread

thread_ids_seen = list({r[1] for r in rows})
print("\n  Per-thread path resolution:")
for tid in thread_ids_seen:
    paths = get_vectorstore_paths_for_thread(tid)
    print("    thread=%s  -> paths=%s" % (tid, paths))

from app.rag.embeddings import get_embeddings
from app.rag.retriever import retrieve
from app.rag.exceptions import DocumentNotIndexedError

real_emb = get_embeddings()
print("\n  Retrieving 'inheritance' from each thread's FAISS index:")
for tid in thread_ids_seen:
    paths = get_vectorstore_paths_for_thread(tid)
    for path in paths:
        print("\n    thread=%s  path=%s" % (tid[:8] + "...", path))
        try:
            chunks = retrieve("inheritance", path, real_emb,
                              use_hybrid_search=False, k=3, rerank_top_k=0)
            for i, c in enumerate(chunks, 1):
                print("      chunk[%d] source=%r  page=%s  score=%.4f" % (
                    i, c.source, c.page, c.relevance_score or 0))
        except DocumentNotIndexedError:
            print("      -> DocumentNotIndexedError")
        except Exception as exc:
            print("      -> %s: %s" % (type(exc).__name__, exc))

print("\n" + SEP)
print("DIAGNOSIS COMPLETE - no patches applied.")
print(SEP)
