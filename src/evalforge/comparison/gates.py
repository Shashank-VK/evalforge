import os
from pathlib import Path
from typing import Optional
import yaml
from evalforge.models import GateConfig, GateEvaluation, Run
from evalforge.exceptions import ValidationFailedError

class GateEvaluator:
    """Evaluates CI regression gates against comparison outcomes."""

    @staticmethod
    def load_gate_config(gate_path: str) -> GateConfig:
        if not os.path.exists(gate_path):
            raise ValidationFailedError(f"Gate configuration file not found at: {gate_path}")
        with open(gate_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return GateConfig(**data)

    @staticmethod
    def evaluate(
        candidate_run: Run,
        regressions: list[dict],
        gate_config: Optional[GateConfig]
    ) -> tuple[bool, list[GateEvaluation]]:
        if not gate_config:
            return True, []

        evals: list[GateEvaluation] = []
        all_passed = True
        metrics = candidate_run.aggregate_metrics or {}

        # 1. Minimum Aggregate Quality Score
        if gate_config.min_aggregate_score is not None:
            actual_score = metrics.get("mean_score", 0.0)
            passed = actual_score >= gate_config.min_aggregate_score
            if not passed:
                all_passed = False
            evals.append(GateEvaluation(
                rule_name="min_aggregate_score",
                threshold=gate_config.min_aggregate_score,
                actual_value=actual_score,
                passed=passed,
                message=f"Candidate quality score {actual_score:.4f} {'passed' if passed else 'FAILED'} (threshold: {gate_config.min_aggregate_score:.4f})"
            ))

        # 2. Maximum Allowed Regressions
        if gate_config.max_allowed_regressions is not None:
            num_regressions = len(regressions)
            passed = num_regressions <= gate_config.max_allowed_regressions
            if not passed:
                all_passed = False
            evals.append(GateEvaluation(
                rule_name="max_allowed_regressions",
                threshold=gate_config.max_allowed_regressions,
                actual_value=num_regressions,
                passed=passed,
                message=f"Regressions detected: {num_regressions} {'passed' if passed else 'FAILED'} (max allowed: {gate_config.max_allowed_regressions})"
            ))

        # 3. Maximum Latency p95
        if gate_config.max_latency_p95_ms is not None:
            p95 = metrics.get("latency_p95_ms", 0.0)
            passed = p95 <= gate_config.max_latency_p95_ms
            if not passed:
                all_passed = False
            evals.append(GateEvaluation(
                rule_name="max_latency_p95_ms",
                threshold=gate_config.max_latency_p95_ms,
                actual_value=p95,
                passed=passed,
                message=f"Latency p95 {p95:.1f}ms {'passed' if passed else 'FAILED'} (threshold: {gate_config.max_latency_p95_ms:.1f}ms)"
            ))

        # 4. Maximum Cost Per Case
        if gate_config.max_cost_per_case_usd is not None:
            completed = metrics.get("completed_cases", candidate_run.completed_cases) or 1
            cost_per_case = metrics.get("total_cost_usd", candidate_run.total_cost_usd) / completed
            passed = cost_per_case <= gate_config.max_cost_per_case_usd
            if not passed:
                all_passed = False
            evals.append(GateEvaluation(
                rule_name="max_cost_per_case_usd",
                threshold=gate_config.max_cost_per_case_usd,
                actual_value=round(cost_per_case, 6),
                passed=passed,
                message=f"Cost per case ${cost_per_case:.6f} {'passed' if passed else 'FAILED'} (threshold: ${gate_config.max_cost_per_case_usd:.6f})"
            ))

        # 5. Required Pass Rate
        if gate_config.required_pass_rate is not None:
            pass_rate = metrics.get("pass_rate", 0.0)
            passed = pass_rate >= gate_config.required_pass_rate
            if not passed:
                all_passed = False
            evals.append(GateEvaluation(
                rule_name="required_pass_rate",
                threshold=gate_config.required_pass_rate,
                actual_value=pass_rate,
                passed=passed,
                message=f"Pass rate {pass_rate:.2%} {'passed' if passed else 'FAILED'} (threshold: {gate_config.required_pass_rate:.2%})"
            ))

        return all_passed, evals
