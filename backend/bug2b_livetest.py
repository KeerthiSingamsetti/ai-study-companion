
# coding: utf-8
# bug2b_livetest.py - BUG 2b live Groq fire for 'which quizzes did I attempt'
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env')

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq

llm = ChatGroq(model=os.getenv('GROQ_MODEL'), api_key=os.getenv('GROQ_API_KEY'), temperature=0)

STUDY_PROGRESS_RESULT_SYSTEM_PROMPT = (
    "Answer the student's performance question using ONLY the structured study-progress data supplied by the tool.\n"
    "The tool returns `quiz_attempts`, `weak_topics`, and `studied_topics` lists. Do not invent, infer, estimate, or embellish any score, quiz attempt, topic, or weakness.\n"
    "If the relevant list is empty, state plainly that no data has been recorded yet. Do not search uploaded documents for this kind of question."
)

tool_result = json.dumps({
    'quiz_attempts' : [{'topic': 'OOP', 'score': '7/10', 'date': '2026-07-29'}],
    'weak_topics'   : [{'topic': 'Polymorphism', 'detail': 'missed 3/5'}],
    'studied_topics': [{'topic': 'Encapsulation'}],
})

# In the real graph, after ToolMessage arrives, chatbot.py builds:
#   [SystemMessage(STUDY_PROGRESS_RESULT_SYSTEM_PROMPT), <all prior messages>, ToolMessage]
# 'all prior messages' includes the original HumanMessage + the AIMessage with tool_call
# But _messages_for_model returns ALL messages when last_message IS a ToolMessage

messages = [
    SystemMessage(content=STUDY_PROGRESS_RESULT_SYSTEM_PROMPT),
    HumanMessage(content='which quizzes did I attempt'),
    ToolMessage(tool_call_id='fake-1', name='get_study_progress', content=tool_result),
]

print("FIRING: 'which quizzes did I attempt' with STUDY_PROGRESS_RESULT_SYSTEM_PROMPT")
print("System prompt length: %d chars" % len(STUDY_PROGRESS_RESULT_SYSTEM_PROMPT))
print("Tool result passed to model:")
print("  " + tool_result)
print()
r = llm.invoke(messages)
print("RAW RESPONSE:")
print(repr(r.content))
print()
print("FORMATTED:")
print(r.content)
print()

cl = r.content.lower()
print("Contains 'weak'/'polymorphi'? -> %s  %s" % (
    ('weak' in cl or 'polymorphi' in cl),
    "<- BLEEDING BUG: weak topics bled into quiz-only response" if ('weak' in cl or 'polymorphi' in cl) else ""
))
print("Contains '7/10'/'OOP'/'quiz'? -> %s" % ('7/10' in cl or 'oop' in cl or 'quiz' in cl))
