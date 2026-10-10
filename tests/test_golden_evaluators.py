import pytest
from evalforge.models import DatasetCase, CaseResult
from evalforge.scorers.contains import ContainsScorer
from evalforge.scorers.rubric import RubricJudgeScorer
from evalforge.scorers.semantic import SemanticSimilarityScorer

GOLDEN_EVALUATOR_FIXTURES = [
    {
        "case": DatasetCase(
            id="golden-01",
            input={"question": "What is the return period?"},
            expected={"contains": ["30 days"], "forbidden": ["never"]}
        ),
        "result": CaseResult(
            run_id="golden-run",
            case_id="golden-01",
            config_id="golden-cfg",
            prompt_rendered="What is the return period?",
            prompt_hash="h1",
            response_text="The return period is 30 days from purchase.",
            status="completed",
            provider="fixture",
            model="fixture-v1",
            created_at="2026-10-10T00:00:00Z"
        ),
        "expected_contains_score": 1.0,
        "expected_band": "pass"
    },
    {
        "case": DatasetCase(
            id="golden-02",
            input={"question": "Can I cancel anytime?"},
            expected={"contains": ["cancel"], "forbidden": ["impossible"]}
        ),
        "result": CaseResult(
            run_id="golden-run",
            case_id="golden-02",
            config_id="golden-cfg",
            prompt_rendered="Can I cancel anytime?",
            prompt_hash="h2",
            response_text="It is impossible to cancel after billing.",
            status="completed",
            provider="fixture",
            model="fixture-v1",
            created_at="2026-10-10T00:00:00Z"
        ),
        "expected_contains_score": 0.0,
        "expected_band": "fail"
    }
]

def test_golden_evaluator_behaviors():
    """Golden test verifying deterministic behavior of evaluators across test suites."""
    contains_scorer = ContainsScorer()

    for item in GOLDEN_EVALUATOR_FIXTURES:
        score = contains_scorer.score_case(item["case"], item["result"])
        assert score.score == item["expected_contains_score"]
        assert score.band == item["expected_band"]
