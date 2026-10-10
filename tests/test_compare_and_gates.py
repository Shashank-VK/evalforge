import pytest
from evalforge.models import Run, Score, GateConfig
from evalforge.storage.repository import Repository
from evalforge.comparison.comparator import RunComparator
from evalforge.comparison.gates import GateEvaluator

@pytest.mark.asyncio
async def test_comparison_and_gate_evaluation(temp_db_path):
    repo = Repository(temp_db_path)

    run_a = Run(
        id="run-baseline",
        name="baseline",
        status="completed",
        experiment_spec={},
        spec_hash="hash_a",
        completed_cases=2,
        total_cost_usd=0.001,
        created_at="2026-10-10T00:00:00Z",
        aggregate_metrics={"mean_score": 0.80, "latency_p50_ms": 30.0, "latency_p95_ms": 50.0}
    )
    run_b = Run(
        id="run-candidate",
        name="candidate",
        status="completed",
        experiment_spec={},
        spec_hash="hash_b",
        completed_cases=2,
        total_cost_usd=0.002,
        created_at="2026-10-10T00:00:00Z",
        aggregate_metrics={"mean_score": 0.90, "latency_p50_ms": 25.0, "latency_p95_ms": 40.0}
    )

    await repo.save_run(run_a)
    await repo.save_run(run_b)

    # Scores
    s_a1 = Score(id="s1", run_id="run-baseline", case_id="c1", config_id="cfg", scorer_name="rubric", score=0.8, passed=True, band="pass", explanation="")
    s_b1 = Score(id="s2", run_id="run-candidate", case_id="c1", config_id="cfg", scorer_name="rubric", score=0.9, passed=True, band="pass", explanation="")
    await repo.save_scores([s_a1, s_b1])

    # 1. Gate passes
    pass_gate = GateConfig(min_aggregate_score=0.85, max_allowed_regressions=0)
    comp_pass = RunComparator.compare("run-baseline", "run-candidate", repo, gate_config=pass_gate)
    assert comp_pass.quality_delta == 0.10
    assert comp_pass.gates_passed is True
    assert len(comp_pass.regressions) == 0

    # 2. Gate fails when threshold too high
    fail_gate = GateConfig(min_aggregate_score=0.95)
    comp_fail = RunComparator.compare("run-baseline", "run-candidate", repo, gate_config=fail_gate)
    assert comp_fail.gates_passed is False

    await repo.aclose()
