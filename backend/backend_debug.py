"""Verify Groq quiz LLM and flashcard generation works."""
import os, sys
from dotenv import load_dotenv
load_dotenv(".env", override=True)

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

model = os.getenv("GROQ_MODEL")
quiz_key = os.getenv("GROQ_QUIZ_API_KEY")
main_key = os.getenv("GROQ_API_KEY")

print(f"Model: {model}")

# Test quiz LLM (used by flashcards)
try:
    llm = ChatGroq(model=model, api_key=quiz_key, temperature=0)
    resp = llm.invoke([
        SystemMessage(content="Return only valid JSON, no prose."),
        HumanMessage(content='Return exactly: {"status": "ok"}')
    ])
    print(f"Quiz LLM OK: {resp.content[:80]}")
except Exception as e:
    print(f"Quiz LLM FAIL: {e}")
    sys.exit(1)

# Test main LLM (used by chat)
try:
    llm2 = ChatGroq(model=model, api_key=main_key, temperature=0)
    resp2 = llm2.invoke([HumanMessage(content="Say hello")])
    print(f"Main LLM OK: {resp2.content[:50]}")
except Exception as e:
    print(f"Main LLM FAIL: {e}")
    sys.exit(1)

print("All LLMs OK - ready to start server")
