import uuid
import re
from evalforge.scorers.base import BaseScorer
from evalforge.models import DatasetCase, CaseResult, Score
from evalforge.constants import PASS_BAND_PASS, PASS_BAND_NEEDS_REVIEW, PASS_BAND_FAIL

class CitationScorer(BaseScorer):
    """Scorer that checks citation formatting and required document chunk references."""
    name = "citation"

    def score_case(self, case: DatasetCase, result: CaseResult) -> Score:
        score_id = str(uuid.uuid4())
        expected_dict = case.expected or {}
        expected_citations = expected_dict.get("citations") or expected_dict.get("relevant_chunk_ids") or []
        if isinstance(expected_citations, str):
            expected_citations = [expected_citations]

        resp_text = result.response_text

        # Find all citation patterns like [doc1#chunk2] or [doc1] or [1]
        found_citations = re.findall(r"\[([a-zA-Z0-9_\-\.:#]+)\]", resp_text)

        if not expected_citations:
            # If no expected citations specified, verify whether text has any citations when grounded
            has_citations = len(found_citations) > 0
            return Score(
                id=score_id,
                run_id=result.run_id,
                case_id=case.id,
                config_id=result.config_id,
                scorer_name=self.name,
                score=1.0 if has_citations else 0.8,
                passed=True,
                band=PASS_BAND_PASS,
                explanation=f"Found {len(found_citations)} citation marker(s) in response.",
                details={"found_citations": found_citations}
            )

        matched = []
        missing = []
        for exp in expected_citations:
            if any(exp.lower() in found.lower() or found.lower() in exp.lower() for found in found_citations) or exp.lower() in resp_text.lower():
                matched.append(exp)
            else:
                missing.append(exp)

        ratio = len(matched) / len(expected_citations)
        score_val = round(ratio, 4)
        band = Score.determine_band(score_val)
        passed = (band == PASS_BAND_PASS)

        explanation = (
            f"Citation check: matched {len(matched)}/{len(expected_citations)} expected citations. "
            f"Found: {found_citations}. Missing: {missing}."
        )

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
                "found_citations": found_citations,
                "matched_expected": matched,
                "missing_expected": missing,
                "ratio": ratio
            }
        )
