from typing import Optional
from evalforge.models import ComparisonResult, GateConfig, Run
from evalforge.storage.repository import Repository
from evalforge.comparison.gates import GateEvaluator
from evalforge.logger import get_logger

logger = get_logger(__name__)

class RunComparator:
    """Compares baseline and candidate evaluation runs and identifies regressions and trade-offs."""

    @staticmethod
    def compare(
        baseline_run_id: str,
        candidate_run_id: str,
        repository: Repository,
        gate_config: Optional[GateConfig] = None
    ) -> ComparisonResult:
        baseline_run = repository.get_run(baseline_run_id)
        if not baseline_run:
            raise ValueError(f"Baseline run {baseline_run_id} not found")

        candidate_run = repository.get_run(candidate_run_id)
        if not candidate_run:
            raise ValueError(f"Candidate run {candidate_run_id} not found")

        b_metrics = baseline_run.aggregate_metrics or {}
        c_metrics = candidate_run.aggregate_metrics or {}

        b_score = b_metrics.get("mean_score", 0.0)
        c_score = c_metrics.get("mean_score", 0.0)
        quality_delta = round(c_score - b_score, 4)

        b_p50 = b_metrics.get("latency_p50_ms", 0.0)
        c_p50 = c_metrics.get("latency_p50_ms", 0.0)
        latency_p50_delta = round(c_p50 - b_p50, 2)

        b_p95 = b_metrics.get("latency_p95_ms", 0.0)
        c_p95 = c_metrics.get("latency_p95_ms", 0.0)
        latency_p95_delta = round(c_p95 - b_p95, 2)

        b_cost = b_metrics.get("total_cost_usd", baseline_run.total_cost_usd)
        c_cost = c_metrics.get("total_cost_usd", candidate_run.total_cost_usd)
        cost_delta = round(c_cost - b_cost, 6)

        # Per-case scores comparison
        b_scores = repository.get_scores(baseline_run_id)
        c_scores = repository.get_scores(candidate_run_id)

        # Index by (case_id, scorer_name)
        b_score_map = {(s.case_id, s.scorer_name): s for s in b_scores}
        c_score_map = {(s.case_id, s.scorer_name): s for s in c_scores}

        regressions = []
        improvements = []

        for key, c_s in c_score_map.items():
            case_id, scorer_name = key
            if key in b_score_map:
                b_s = b_score_map[key]
                score_diff = round(c_s.score - b_s.score, 4)

                if score_diff < -0.05 or (b_s.passed and not c_s.passed):
                    regressions.append({
                        "case_id": case_id,
                        "scorer": scorer_name,
                        "baseline_score": b_s.score,
                        "candidate_score": c_s.score,
                        "baseline_band": b_s.band,
                        "candidate_band": c_s.band,
                        "delta": score_diff,
                        "baseline_explanation": b_s.explanation,
                        "candidate_explanation": c_s.explanation
                    })
                elif score_diff > 0.05 or (not b_s.passed and c_s.passed):
                    improvements.append({
                        "case_id": case_id,
                        "scorer": scorer_name,
                        "baseline_score": b_s.score,
                        "candidate_score": c_s.score,
                        "baseline_band": b_s.band,
                        "candidate_band": c_s.band,
                        "delta": score_diff
                    })

        gates_passed, gate_evals = GateEvaluator.evaluate(candidate_run, regressions, gate_config)

        return ComparisonResult(
            baseline_run_id=baseline_run.id,
            candidate_run_id=candidate_run.id,
            baseline_name=baseline_run.name,
            candidate_name=candidate_run.name,
            quality_delta=quality_delta,
            latency_p50_delta_ms=latency_p50_delta,
            latency_p95_delta_ms=latency_p95_delta,
            cost_delta_usd=cost_delta,
            baseline_metrics=b_metrics,
            candidate_metrics=c_metrics,
            regressions=regressions,
            improvements=improvements,
            gates_passed=gates_passed,
            gate_evaluations=gate_evals
        )
