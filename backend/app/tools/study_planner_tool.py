"""Study-plan generation tool."""
from __future__ import annotations
import json
from typing import Any
from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import ValidationError
from app.db import crud
from app.db.session import SessionLocal
from app.rag.topic_extractor import extract_document_topics
from app.schemas.planner import StudyPlanResponse
from app.config import DEFAULT_USER_ID
from app.tools.memory_tool import record_studied_topic

class StudyPlanGenerationError(RuntimeError): pass

def generate_study_plan(llm: Any, document_id: str, topics: list[str] | None = None, num_days: int = 7, exam_date: str | None = None) -> StudyPlanResponse:
    db = SessionLocal()
    try:
        document = crud.get_document(db, document_id)
        if not document: raise StudyPlanGenerationError("The requested document does not exist.")
        selected_topics = topics or extract_document_topics(document_id, llm)
        if not selected_topics: raise StudyPlanGenerationError("No topics could be extracted from this document.")
        shape = {"type":"tool_result","tool":"study_planner","document_id":document_id,"num_days":num_days,"days":[{"day":1,"topics":["topic"],"focus":"focus","tasks":["task"]}]}
        prompt = f"Create a logical {num_days}-day study plan for topics {selected_topics}. Exam date: {exam_date or 'not provided'}. Include a lighter review day near the end only when an exam date is provided. Return ONLY JSON matching: {json.dumps(shape)}"
        raw = str(llm.invoke([SystemMessage(content="Return only valid JSON. Do not use markdown."), HumanMessage(content=prompt)]).content)
        try: result = StudyPlanResponse.model_validate_json(raw)
        except ValidationError:
            raw = str(llm.invoke([SystemMessage(content="Return ONLY corrected valid JSON matching the requested schema."), HumanMessage(content=prompt)]).content)
            result = StudyPlanResponse.model_validate_json(raw)
        if result.document_id != document_id or result.num_days != num_days: raise StudyPlanGenerationError("Generated plan metadata did not match the request.")
        crud.log_study_event(db, thread_id=document.thread_id, document_id=document_id, event_type="study_plan_generated", topic=", ".join(selected_topics[:3]))
        for topic in selected_topics[:3]: record_studied_topic(db, DEFAULT_USER_ID, topic, document_id)
        return result
    except (ValidationError, ValueError) as error:
        raise StudyPlanGenerationError("The planner model did not return valid plan JSON.") from error
    finally: db.close()

def create_study_planner_tool(llm: Any) -> BaseTool:
    @tool(response_format="content_and_artifact")
    def generate_document_study_plan(config: RunnableConfig, num_days: int = 7, exam_date: str | None = None) -> tuple[str, dict[str, Any]]:
        """Create a study plan for the active uploaded document when the user asks for an exam schedule or study plan."""
        thread_id = config.get("configurable", {}).get("thread_id")
        db = SessionLocal()
        try:
            documents = crud.list_documents_for_thread(db, thread_id) if thread_id else []
            if len(documents) != 1: return "Please keep one uploaded document in this conversation before generating a study plan.", {}
            result = generate_study_plan(llm, documents[0].id, num_days=num_days, exam_date=exam_date)
            return "Your study plan is ready.", result.model_dump(mode="json")
        except StudyPlanGenerationError as error: return str(error), {}
        finally: db.close()
    return generate_document_study_plan
