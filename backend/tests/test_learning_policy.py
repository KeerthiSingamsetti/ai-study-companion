from types import SimpleNamespace

from app.services.learning import classify_growth, choose_adaptive_concept, normalize_concept_name, repeated_mistake_detected


def test_growth_classifies_improving():
    assert classify_growth(50, 54) == "improving"


def test_growth_classifies_stable():
    assert classify_growth(70, 69) == "stable"


def test_growth_classifies_needs_attention():
    assert classify_growth(70, 66) == "needs_attention"


def test_repeated_mistake_threshold_is_three_in_latest_ten():
    assert repeated_mistake_detected([20, 40, 100, 100]) is False
    assert repeated_mistake_detected([20, 40, 59, 100]) is True


def test_adaptive_selection_uses_mastery_and_mistake_history():
    atp = SimpleNamespace(id="atp")
    dna = SimpleNamespace(id="dna")
    selected, difficulty = choose_adaptive_concept(
        [(atp, SimpleNamespace(mastery_score=60)), (dna, SimpleNamespace(mastery_score=55))],
        {"atp": 2},
    )
    assert selected is atp
    assert difficulty == "medium"


def test_concept_normalization_is_stable():
    assert normalize_concept_name(" ATP-synthesis! ") == "atp synthesis"
