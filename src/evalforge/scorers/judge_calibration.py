import json
import os
from typing import Any, Callable, Optional
from evalforge.models import Score
from evalforge.logger import get_logger

logger = get_logger(__name__)

class JudgeCalibrationReport:
    """Stores calibration analysis results including bias detections and agreement rates."""
    def __init__(self, data: dict[str, Any]):
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        return self.data

class JudgeCalibrator:
    """Calibrates evaluation judges against human labels and analyzes position and verbosity bias."""

    @staticmethod
    def test_order_swapped_pairwise(
        pairs: list[tuple[str, str]], # (text_a, text_b)
        judge_fn: Callable[[str, str], int] # returns 1 if first preferred, 2 if second, 0 if tie
    ) -> dict[str, Any]:
        """Runs pairwise comparisons in forward (A, B) and reversed (B, A) order.
        Detects position bias (favoring whichever candidate is shown first).
        """
        total = len(pairs)
        if total == 0:
            return {"total_pairs": 0, "position_bias_rate": 0.0, "consistency_rate": 1.0}

        consistent_count = 0
        first_position_bias_count = 0

        for text_a, text_b in pairs:
            # Order 1: (A, B)
            res_forward = judge_fn(text_a, text_b)
            # Order 2: (B, A)
            res_reverse = judge_fn(text_b, text_a)

            # If judge picked 1 in forward, they picked A. In reverse, picking A means returning 2.
            if res_forward == 1 and res_reverse == 2:
                consistent_count += 1
            elif res_forward == 2 and res_reverse == 1:
                consistent_count += 1
            elif res_forward == 0 and res_reverse == 0:
                consistent_count += 1
            else:
                # Inconsistency. Did judge favor position 1 in both?
                if res_forward == 1 and res_reverse == 1:
                    first_position_bias_count += 1

        consistency_rate = round(consistent_count / total, 4)
        position_bias_rate = round(first_position_bias_count / total, 4)

        return {
            "total_pairs": total,
            "consistent_comparisons": consistent_count,
            "consistency_rate": consistency_rate,
            "position_bias_count": first_position_bias_count,
            "position_bias_rate": position_bias_rate,
            "bias_verdict": "Low position bias" if position_bias_rate < 0.10 else "Noticeable position bias detected"
        }

    @staticmethod
    def analyze_verbosity_bias(results: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyzes whether longer responses systematically correlate with higher scores."""
        if not results:
            return {"sample_size": 0, "verbosity_correlation": 0.0, "status": "no data"}

        lengths = [len(r.get("response_text", "").split()) for r in results]
        scores = [r.get("score", 0.0) for r in results]

        n = len(lengths)
        if n < 2 or len(set(lengths)) == 1 or len(set(scores)) == 1:
            return {"sample_size": n, "verbosity_correlation": 0.0, "status": "insufficient variance"}

        # Pearson correlation
        mean_len = sum(lengths) / n
        mean_score = sum(scores) / n
        cov = sum((lengths[i] - mean_len) * (scores[i] - mean_score) for i in range(n))
        var_len = sum((l - mean_len) ** 2 for l in lengths)
        var_score = sum((s - mean_score) ** 2 for s in scores)

        if var_len == 0 or var_score == 0:
            corr = 0.0
        else:
            corr = round(cov / ((var_len * var_score) ** 0.5), 4)

        return {
            "sample_size": n,
            "verbosity_correlation": corr,
            "status": "Moderate/High verbosity bias" if corr > 0.40 else "Neutral verbosity impact"
        }

    @staticmethod
    def calibrate_against_human_labels(
        scores: list[Score],
        human_labels_path: str = "fixtures/calibration_labels.json"
    ) -> dict[str, Any]:
        """Calibrates judge scores against committed human-labeled ground truth."""
        if not os.path.exists(human_labels_path):
            return {"calibrated": False, "reason": f"Labels file {human_labels_path} not found"}

        with open(human_labels_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        labels = data.get("labels", data)
        # map case_id -> human judgment
        human_map = {item["case_id"]: item for item in labels if "case_id" in item}

        agreements = 0
        disagreements = 0
        disagreement_cases = []
        tested_cases = 0

        for score in scores:
            if score.case_id in human_map:
                tested_cases += 1
                human_item = human_map[score.case_id]
                expected_band = human_item.get("expected_band", human_item.get("human_rating"))
                # Match band
                if score.band == expected_band or (score.passed and expected_band == "pass") or (not score.passed and expected_band == "fail"):
                    agreements += 1
                else:
                    disagreements += 1
                    disagreement_cases.append({
                        "case_id": score.case_id,
                        "judge_band": score.band,
                        "human_band": expected_band,
                        "judge_score": score.score,
                        "human_notes": human_item.get("notes", ""),
                        "judge_explanation": score.explanation
                    })

        if tested_cases == 0:
            return {"calibrated": False, "reason": "No matching cases between judge scores and calibration labels"}

        agreement_rate = round(agreements / tested_cases, 4)
        disagreement_rate = round(disagreements / tested_cases, 4)

        return {
            "calibrated": True,
            "tested_sample_size": tested_cases,
            "agreement_rate": agreement_rate,
            "disagreement_rate": disagreement_rate,
            "confidence_level": 0.95,
            "disagreements": disagreement_cases,
            "verdict": "High Judge Calibration Agreement" if agreement_rate >= 0.85 else "Judge requires rubric tuning"
        }
