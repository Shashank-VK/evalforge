import uuid
import re
from evalforge.scorers.base import BaseScorer
from evalforge.models import DatasetCase, CaseResult, Score
from evalforge.constants import PASS_BAND_PASS, PASS_BAND_NEEDS_REVIEW, PASS_BAND_FAIL

class ContainsScorer(BaseScorer):
    """Scorer that checks for required factual elements and detects forbidden claims.
    If a forbidden claim is detected, the case is immediately failed with score 0.0.
    """
    name = "contains"

    def score_case(self, case: DatasetCase, result: CaseResult) -> Score:
        score_id = str(uuid.uuid4())
        expected_dict = case.expected or {}
        
        # Extract required items
        required_list = expected_dict.get("contains") or expected_dict.get("required_facts") or []
        if isinstance(required_list, str):
            required_list = [required_list]

        # Extract forbidden items
        forbidden_list = expected_dict.get("forbidden") or expected_dict.get("forbidden_claims") or []
        if isinstance(forbidden_list, str):
            forbidden_list = [forbidden_list]

        text_lower = result.response_text.lower()

        # Check forbidden claims first
        violations = []
        for forbidden in forbidden_list:
            if forbidden.lower() in text_lower:
                violations.append(forbidden)

        if violations:
            return Score(
                id=score_id,
                run_id=result.run_id,
                case_id=case.id,
                config_id=result.config_id,
                scorer_name=self.name,
                score=0.0,
                passed=False,
                band=PASS_BAND_FAIL,
                explanation=f"Safety violation: response contains forbidden claim(s): {', '.join(violations)}.",
                details={"forbidden_violations": violations, "required_matched": 0, "total_required": len(required_list)}
            )

        if not required_list:
            return Score(
                id=score_id,
                run_id=result.run_id,
                case_id=case.id,
                config_id=result.config_id,
                scorer_name=self.name,
                score=1.0,
                passed=True,
                band=PASS_BAND_PASS,
                explanation="No required facts specified; no forbidden claims violated.",
                details={"matched_keywords": [], "missing_keywords": []}
            )

        matched = []
        missing = []
        for req in required_list:
            if req.lower() in text_lower:
                matched.append(req)
            else:
                missing.append(req)

        match_ratio = len(matched) / len(required_list)
        score_val = round(match_ratio, 4)
        band = Score.determine_band(score_val)
        passed = (band == PASS_BAND_PASS)

        if match_ratio == 1.0:
            explanation = f"All {len(required_list)} required fact(s) present: {', '.join(matched)}."
        elif match_ratio >= 0.5:
            explanation = f"Partial match ({len(matched)}/{len(required_list)}). Matched: {matched}. Missing: {missing}."
        else:
            explanation = f"Failed factual check. Missing required fact(s): {missing}."

        return Score(
            id=score_id,
            run_id=result.run_id,
            case_id=case.id,
            config_id=result.config_id,
            scorer_name=self.name,
            score=score_val,
            passed=passed,
            band=band,
            explanation=explanation,
            details={
                "matched_keywords": matched,
                "missing_keywords": missing,
                "match_ratio": match_ratio
            }
        )
