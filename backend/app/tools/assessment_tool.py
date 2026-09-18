"""Grounded generation of open-ended assessment questions.

Multiple-choice quizzes can be answered by recognition; the PRD also asks for
open-ended assessment that requires the learner to *explain*.  Generation and
grading both stay grounded in the uploaded material — the reference answer is
built only from retrieved project evidence, never from outside knowledge.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.rag.retriever import RetrievedChunk

RUBRIC = (
    "Assess conceptual understanding, factual accuracy, relevance, completeness and the "
    "quality of reasoning. Award credit for correct equivalent explanations supported by "
    "the retrieved evidence."
)


class AssessmentGenerationError(RuntimeError):
    """Raised when a grounded open-ended question cannot be generated safely."""


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks as bounded, traceable assessment evidence."""
    return "\n\n".join(
        f"[SOURCE:{index}] {Path(chunk.source).name}, "
        f"page {chunk.page + 1 if chunk.page is not None else 'unknown'}\n{chunk.content}"
        for index, chunk in enumerate(chunks, start=1)
    )


def _content(response: Any) -> str:
    content = getattr(response, "content", "")
    return content.strip() if isinstance(content, str) else str(content).strip()


def _required_shape(*, concept: str, difficulty: str, count: int) -> dict:
    return {
        "questions": [
            {
                "question": f"...{concept}...",
                "reference_answer": "A model answer grounded strictly in the evidence.",
                "rubric": RUBRIC,
                "source_citation": "filename.pdf, page 14",
            }
        ] * count,
    }


def generate_open_ended_questions(
    llm: BaseChatModel,
    *,
    concept: str,
    difficulty: str,
    num_questions: int,
    context: str,
    citation_hint: str | None = None,
) -> list[dict[str, str]]:
    """Generate explanation-style questions with reference answers from evidence.

    One corrective retry is attempted when the model returns unparseable JSON,
    matching the quiz generator's existing contract-with-retry behaviour.
    """
    if not context.strip():
        raise AssessmentGenerationError("No relevant document content was found for this concept.")

    shape = _required_shape(concept=concept, difficulty=difficulty, count=num_questions)
    system = SystemMessage(
        content=(
            "You design short open-ended assessment questions for a study companion. "
            "You will be given retrieved chunks of the student's own course material.\n\n"
            "RULES:\n"
            "1. Ask questions that require the student to EXPLAIN, COMPARE, DERIVE or APPLY — "
            "not to recall wording from the text.\n"
            "2. The reference_answer must be answerable entirely from the provided evidence. "
            "Never use outside knowledge or invent facts.\n"
            "3. The rubric must name the specific ideas a strong answer should contain.\n"
            "4. Questions must be unambiguous and self-contained (no 'as mentioned above').\n"
            "5. Return ONLY valid JSON, no markdown fences, matching the required shape exactly."
        )
    )
    prompt = HumanMessage(
        content=(
            f"Create exactly {num_questions} {difficulty} open-ended question(s) about "
            f"{concept!r} from this material.\n"
            f"Required JSON shape:\n{json.dumps(shape)}\n\n"
            f"Cite provenance as {citation_hint or 'filename.pdf, page N'} where possible.\n\n"
            f"Document context:\n{context}"
        )
    )

    def parse(raw: str) -> list[dict[str, str]]:
        parsed = json.loads(raw)
        questions = parsed.get("questions") if isinstance(parsed, dict) else None
        if not isinstance(questions, list) or not questions:
            raise ValueError("The assessment model returned no questions.")
        cleaned: list[dict[str, str]] = []
        for item in questions:
            if not isinstance(item, dict) or not str(item.get("question", "")).strip():
                raise ValueError("An assessment question was malformed.")
            cleaned.append(
                {
                    "question": str(item["question"]).strip(),
                    "reference_answer": str(item.get("reference_answer", "")).strip(),
                    "rubric": str(item.get("rubric") or RUBRIC).strip(),
                    "source_citation": (
                        str(item["source_citation"]).strip() if item.get("source_citation") else None
                    ),
                }
            )
        return cleaned

    raw = _content(llm.invoke([system, prompt]))
    try:
        return parse(raw)
    except (ValueError, json.JSONDecodeError) as first_error:
        retry = HumanMessage(
            content=(
                "Your previous response was invalid. Return ONLY valid JSON matching this exact "
                f"shape: {json.dumps(shape)}\nPrevious response:\n{raw}"
            )
        )
        try:
            return parse(_content(llm.invoke([system, prompt, retry])))
        except (ValueError, json.JSONDecodeError, ValidationError) as retry_error:
            raise AssessmentGenerationError(
                "The assessment model did not return valid question JSON."
            ) from retry_error
