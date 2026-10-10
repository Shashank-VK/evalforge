import pytest
from evalforge.models import DatasetCase, CaseResult
from evalforge.scorers.exact_match import ExactMatchScorer
from evalforge.scorers.contains import ContainsScorer
from evalforge.scorers.json_schema import JsonSchemaScorer
from evalforge.scorers.semantic import SemanticSimilarityScorer
from evalforge.scorers.citation import CitationScorer
from evalforge.scorers.rubric import RubricJudgeScorer
from evalforge.constants import PASS_BAND_PASS, PASS_BAND_NEEDS_REVIEW, PASS_BAND_FAIL

def make_result(text: str) -> CaseResult:
    return CaseResult(
        run_id="run-1",
        case_id="case-1",
        config_id="cfg-1",
        prompt_rendered="test prompt",
        prompt_hash="h1",
        response_text=text,
        status="completed",
        provider="mock",
        model="mock-v1",
        created_at="2026-10-10T00:00:00Z"
    )

def test_exact_match_normalized_structured():
    scorer = ExactMatchScorer()
    case = DatasetCase(
        id="c1",
        input={"task": "id"},
        expected={"exact_match": "{\"status\": \"ok\", \"code\": 200}"}
    )
    # Match with different whitespace
    res_pass = make_result("{\n  \"status\": \"ok\",\n  \"code\": 200\n}")
    score_pass = scorer.score_case(case, res_pass)
    assert score_pass.passed is True
    assert score_pass.score == 1.0
    assert score_pass.band == PASS_BAND_PASS

    res_fail = make_result("{\"status\": \"error\"}")
    score_fail = scorer.score_case(case, res_fail)
    assert score_fail.passed is False
    assert score_fail.score == 0.0
    assert score_fail.band == PASS_BAND_FAIL

def test_contains_forbidden_claims_immediate_fail():
    scorer = ContainsScorer()
    case = DatasetCase(
        id="c2",
        input={"q": "refund"},
        expected={
            "contains": ["full refund", "14 days"],
            "forbidden": ["never refundable", "100% guaranteed"]
        }
    )

    # Valid response
    res_clean = make_result("You are eligible for a full refund within 14 days.")
    score_clean = scorer.score_case(case, res_clean)
    assert score_clean.passed is True
    assert score_clean.score == 1.0
    assert score_clean.band == PASS_BAND_PASS

    # Response with forbidden claim
    res_forbidden = make_result("A full refund is 100% guaranteed anytime.")
    score_forbidden = scorer.score_case(case, res_forbidden)
    assert score_forbidden.passed is False
    assert score_forbidden.score == 0.0
    assert score_forbidden.band == PASS_BAND_FAIL
    assert "forbidden claim" in score_forbidden.explanation.lower()

def test_json_schema_validation():
    scorer = JsonSchemaScorer()
    case = DatasetCase(
        id="c3",
        input={"q": "data"},
        expected={
            "json_schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
                "required": ["name", "age"]
            }
        }
    )

    res_valid = make_result('{"name": "Alice", "age": 30}')
    s_valid = scorer.score_case(case, res_valid)
    assert s_valid.passed is True
    assert s_valid.score == 1.0

    res_invalid = make_result('{"name": "Bob"}')
    s_invalid = scorer.score_case(case, res_invalid)
    assert s_invalid.passed is False
    assert s_invalid.score == 0.0
    assert "validation failed" in s_invalid.explanation.lower()

def test_semantic_similarity_tolerant():
    scorer = SemanticSimilarityScorer()
    case = DatasetCase(
        id="c4",
        input={"q": "greeting"},
        expected={"answer": "Customer subscriptions can be terminated anytime in account settings."}
    )

    # Paraphrased answer
    res_paraphrase = make_result("You can easily terminate your customer subscription via the account settings console at any time.")
    s_score = scorer.score_case(case, res_paraphrase)
    assert s_score.score > 0.50
    assert s_score.band in (PASS_BAND_PASS, PASS_BAND_NEEDS_REVIEW)
    assert "semantic similarity" in s_score.explanation.lower()

def test_citation_scorer():
    scorer = CitationScorer()
    case = DatasetCase(
        id="c5",
        input={"q": "policy"},
        expected={"citations": ["doc-billing#chunk1"]}
    )

    res_cited = make_result("Per our policy [doc-billing#chunk1], accounts receive prorated credits.")
    s_cited = scorer.score_case(case, res_cited)
    assert s_cited.passed is True
    assert s_cited.score == 1.0

    res_uncited = make_result("Accounts receive prorated credits.")
    s_uncited = scorer.score_case(case, res_uncited)
    assert s_uncited.passed is False
    assert s_uncited.score == 0.0

def test_rubric_judge_scorer_explanation_and_bands():
    scorer = RubricJudgeScorer()
    case = DatasetCase(
        id="c6",
        input={"question": "How do I reset my password?"},
        expected={"contains": ["settings", "password", "email"]}
    )

    res_good = make_result("To reset your password, visit account settings and submit your email for a secure link.")
    score_good = scorer.score_case(case, res_good)
    assert score_good.score >= 0.75
    assert score_good.band == PASS_BAND_PASS
    assert len(score_good.explanation) > 10
    assert "completeness" in score_good.details["sub_scores"]
