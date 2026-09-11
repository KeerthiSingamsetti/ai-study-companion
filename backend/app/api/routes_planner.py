from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_quiz_llm
from app.schemas.planner import StudyPlanRequest, StudyPlanResponse
from app.tools.study_planner_tool import StudyPlanGenerationError, generate_study_plan

router = APIRouter(prefix="/planner", tags=["planner"])
@router.post("/generate", response_model=StudyPlanResponse)
def generate_plan(payload: StudyPlanRequest, llm: Annotated[object, Depends(get_quiz_llm)]) -> StudyPlanResponse:
    try: return generate_study_plan(llm, payload.document_id, payload.topics, payload.num_days, payload.exam_date)
    except StudyPlanGenerationError as error: raise HTTPException(status_code=422, detail=str(error)) from error
