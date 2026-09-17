from langchain_core.messages import AIMessage
from app.services.grading import grade_open_ended_answer


class StaticLLM:
    def __init__(self):
        self.messages = []

    def invoke(self, _messages):
        self.messages = _messages
        return AIMessage(content='{"understanding":80,"accuracy":70,"concepts_covered":["ATP"],"concepts_missing":["gradient"],"feedback":"Good core explanation."}')


def test_open_ended_grading_returns_validated_structure():
    llm = StaticLLM()
    grade = grade_open_ended_answer(llm, question="What makes ATP?", answer="Mitochondria", reference_answer="Mitochondria use a gradient.", retrieved_context="The mitochondria make ATP using a proton gradient.")
    assert grade.overall_score == 75
    assert grade.concepts_missing == ["gradient"]
    assert "equivalent explanations" in str(llm.messages[0].content)
    assert "Retrieved project evidence" in str(llm.messages[1].content)


def test_equivalent_wording_receives_a_high_grade():
    """A correct paraphrase must not be penalized for differing from the exemplar."""
    llm = StaticLLM()
    grade = grade_open_ended_answer(
        llm,
        question="How is ATP made?",
        answer="Cells use the proton difference across the inner mitochondrial membrane to power ATP production.",
        reference_answer="ATP synthase uses the proton gradient across the inner mitochondrial membrane to make ATP.",
        retrieved_context="ATP synthase is powered by the proton gradient across the inner mitochondrial membrane.",
    )

    assert grade.understanding >= 80
    assert grade.accuracy >= 70
    assert grade.overall_score >= 75
