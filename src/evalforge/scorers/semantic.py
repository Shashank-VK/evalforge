import uuid
import re
from evalforge.scorers.base import BaseScorer
from evalforge.models import DatasetCase, CaseResult, Score
from evalforge.constants import PASS_BAND_PASS, PASS_BAND_NEEDS_REVIEW, PASS_BAND_FAIL

def tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())

def token_f1_similarity(ref_tokens: list[str], resp_tokens: list[str]) -> float:
    s_ref, s_resp = set(ref_tokens), set(resp_tokens)
    if not s_ref and not s_resp:
        return 1.0
    if not s_ref or not s_resp:
        return 0.0
    intersection = len(s_ref & s_resp)
    if intersection == 0:
        # Check stem-like prefix matches (e.g. subscription vs subscriptions)
        soft_matches = 0
        for r in s_ref:
            if any(r.startswith(c) or c.startswith(r) for c in s_resp if min(len(r), len(c)) >= 4):
                soft_matches += 1
        intersection = soft_matches

    precision = intersection / len(s_resp) if s_resp else 0.0
    recall = intersection / len(s_ref) if s_ref else 0.0
    if precision + recall == 0:
        return 0.0
    return (2 * precision * recall) / (precision + recall)

def char_ngram_similarity(text1: str, text2: str, n: int = 3) -> float:
    def get_ngrams(s: str) -> set[str]:
        cleaned = re.sub(r"\s+", " ", s.lower().strip())
        return {cleaned[i:i+n] for i in range(max(len(cleaned) - n + 1, 0))}
    
    ng1 = get_ngrams(text1)
    ng2 = get_ngrams(text2)
    if not ng1 and not ng2:
        return 1.0
    if not ng1 or not ng2:
        return 0.0
    intersection = len(ng1 & ng2)
    return (2 * intersection) / (len(ng1) + len(ng2))

class SemanticSimilarityScorer(BaseScorer):
    """Scorer calculating token and n-gram overlap similarity against a reference answer.
    Provides tolerant evaluation of generative answers without requiring strict exact matching.
    """
    name = "semantic_similarity"

    def score_case(self, case: DatasetCase, result: CaseResult) -> Score:
        score_id = str(uuid.uuid4())
        expected_dict = case.expected or {}
        reference = (
            expected_dict.get("answer") or
            expected_dict.get("expected_answer") or
            expected_dict.get("exact_match") or
            ""
        )

        if not reference:
            return Score(
                id=score_id,
                run_id=result.run_id,
                case_id=case.id,
                config_id=result.config_id,
                scorer_name=self.name,
                score=1.0,
                passed=True,
                band=PASS_BAND_PASS,
                explanation="No reference answer specified; semantic similarity skipped.",
                details={"skipped": True}
            )

        resp_text = result.response_text
        t_ref = tokenize(reference)
        t_resp = tokenize(resp_text)

        tok_f1 = token_f1_similarity(t_ref, t_resp)
        ngram_sim = char_ngram_similarity(reference, resp_text, n=3)

        # Composite score: n-gram captures fuzzy subword stems and phrasing, token F1 captures exact keywords
        sim_score = round(0.4 * tok_f1 + 0.6 * ngram_sim, 4)
        band = Score.determine_band(sim_score)
        passed = (band in (PASS_BAND_PASS, PASS_BAND_NEEDS_REVIEW))

        explanation = (
            f"Semantic similarity score: {sim_score:.2f} (token F1: {tok_f1:.2f}, 3-gram: {ngram_sim:.2f}). "
            f"Assigned band '{band}'."
        )

        return Score(
            id=score_id,
            run_id=result.run_id,
            case_id=case.id,
            config_id=result.config_id,
            scorer_name=self.name,
            score=sim_score,
            passed=passed,
            band=band,
            explanation=explanation,
            details={
                "token_similarity": round(tok_f1, 4),
                "ngram_similarity": round(ngram_sim, 4),
                "composite_score": sim_score
            }
        )
