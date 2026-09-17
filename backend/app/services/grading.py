"""Schema-validated grading for open-ended answers."""
from __future__ import annotations
import json
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from app.schemas.assessment import OpenEndedGrade


class GradingError(RuntimeError):
    pass


def grade_open_ended_answer(
    llm: Any, *, question: str, answer: str, reference_answer: str,
    retrieved_context: str, rubric: str = "Assess conceptual understanding, factual accuracy, relevance, and reasoning.",
) -> OpenEndedGrade:
    """Grade against retrieved project evidence, with the reference as an exemplar."""
    response = llm.invoke([
        SystemMessage(content=("Grade the student against retrieved project evidence and the rubric. "
            "The reference answer is an exemplar, not the only acceptable wording: award credit for "
            "correct equivalent explanations supported by the evidence. Return JSON with "
            "understanding (0-100), accuracy (0-100), concepts_covered, concepts_missing, feedback. "
            "Do not use outside knowledge.")),
        HumanMessage(content=(f"Question: {question}\nRubric: {rubric}\nRetrieved project evidence: "
            f"{retrieved_context}\nReference exemplar: {reference_answer}\nStudent answer: {answer}")),
    ])
    raw = getattr(response, "content", response)
    try:
        return OpenEndedGrade.model_validate_json(str(raw))
    except Exception as error:
        raise GradingError("The grading model did not return a valid structured grade.") from error
