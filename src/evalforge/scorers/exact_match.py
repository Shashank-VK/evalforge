import json
import uuid
from evalforge.scorers.base import BaseScorer
from evalforge.models import DatasetCase, CaseResult, Score
from evalforge.constants import PASS_BAND_PASS, PASS_BAND_FAIL

class ExactMatchScorer(BaseScorer):
    """Normalized exact match scorer for structured outputs (IDs, category codes, booleans, canonical JSON).
    Note: Exact match is intentionally not recommended for free-form generative text.
    """
    name = "exact_match"

    def score_case(self, case: DatasetCase, result: CaseResult) -> Score:
        score_id = str(uuid.uuid4())
        if not case.expected or "exact_match" not in case.expected:
            return Score(
                id=score_id,
                run_id=result.run_id,
                case_id=case.id,
                config_id=result.config_id,
                scorer_name=self.name,
                score=1.0,
                passed=True,
                band=PASS_BAND_PASS,
                explanation="No exact_match expectation specified; default pass for structured check.",
                details={"skipped": True}
            )

        expected_val = str(case.expected["exact_match"]).strip()
        actual_val = result.response_text.strip()

        # Try JSON normalization if both look like JSON
        matched = False
        if (expected_val.startswith("{") and expected_val.endswith("}")) or \
           (expected_val.startswith("[") and expected_val.endswith("]")):
            try:
                exp_json = json.loads(expected_val)
                act_json = json.loads(actual_val)
                matched = (exp_json == act_json)
            except Exception:
                matched = (expected_val.lower() == actual_val.lower())
        else:
            # Case-insensitive whitespace-normalized match
            matched = (expected_val.lower() == actual_val.lower())

        score_val = 1.0 if matched else 0.0
        band = PASS_BAND_PASS if matched else PASS_BAND_FAIL
        explanation = (
            f"Normalized exact match succeeded: expected '{expected_val}' matched actual."
            if matched else
            f"Normalized exact match failed: expected '{expected_val}', got '{actual_val}'."
        )

        return Score(
            id=score_id,
            run_id=result.run_id,
            case_id=case.id,
            config_id=result.config_id,
            scorer_name=self.name,
            score=score_val,
            passed=matched,
            band=band,
            explanation=explanation,
            details={"expected": expected_val, "actual": actual_val, "matched": matched}
        )
