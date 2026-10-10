import pytest
from evalforge.models import Score
from evalforge.scorers.judge_calibration import JudgeCalibrator

def test_order_swapped_pairwise_position_bias():
    """Verifies detection of position bias via order-swapped candidate pairs."""
    # Symmetrical unbiased judge
    pairs = [
        ("Good answer with citations", "Vague answer without detail"),
        ("Detailed policy reference", "Short ungrounded answer")
    ]
    # Unbiased judge picks the better answer regardless of order
    def unbiased_judge(a, b):
        return 1 if "Good" in a or "Detailed" in a else 2

    res_unbiased = JudgeCalibrator.test_order_swapped_pairwise(pairs, unbiased_judge)
    assert res_unbiased["consistency_rate"] == 1.0
    assert res_unbiased["position_bias_rate"] == 0.0

    # Biased judge always picks position 1
    def position_biased_judge(a, b):
        return 1

    res_biased = JudgeCalibrator.test_order_swapped_pairwise(pairs, position_biased_judge)
    assert res_biased["consistency_rate"] == 0.0
    assert res_biased["position_bias_rate"] == 1.0

def test_verbosity_bias_analysis():
    """Verifies calculation of correlation between response length and scores."""
    results = [
        {"response_text": "short text", "score": 0.5},
        {"response_text": "medium length text here with more tokens", "score": 0.75},
        {"response_text": "a very long detailed text with many more tokens and words included", "score": 0.95}
    ]
    report = JudgeCalibrator.analyze_verbosity_bias(results)
    assert report["verbosity_correlation"] > 0.80

def test_human_calibration_agreement():
    """Verifies calibration metrics calculated against committed calibration labels."""
    sample_scores = [
        Score(
            id="s1",
            run_id="r1",
            case_id="case-001",
            config_id="c1",
            scorer_name="contains",
            score=1.0,
            passed=True,
            band="pass",
            explanation="Pass"
        ),
        Score(
            id="s2",
            run_id="r1",
            case_id="case-002",
            config_id="c1",
            scorer_name="contains",
            score=1.0,
            passed=True,
            band="pass",
            explanation="Pass"
        )
    ]
    report = JudgeCalibrator.calibrate_against_human_labels(sample_scores, "fixtures/calibration_labels.json")
    assert report["calibrated"] is True
    assert report["agreement_rate"] == 1.0
    assert report["tested_sample_size"] == 2
