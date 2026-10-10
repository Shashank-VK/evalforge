import pytest
from evalforge.models import ExperimentSpec, GateConfig
from evalforge.runner.planner import Planner
from evalforge.runner.executor import Executor
from evalforge.scorers.registry import ScorerRegistry
from evalforge.comparison.comparator import RunComparator
from evalforge.storage.repository import Repository

@pytest.mark.asyncio
async def test_offline_fixture_runs_produce_identical_scores_and_ordering(temp_db_path):
    """Proves that repeated offline fixture runs produce 100% identical scores and ordering without network."""
    repo = Repository(temp_db_path)
    spec = Planner.load_experiment_spec("experiments/ci_experiment.yaml")

    executor = Executor(repo)

    # Run 1
    run1 = await executor.run_experiment(spec)
    scores1 = await ScorerRegistry.execute_scorers_for_run(run1.id, spec, repo)
    run1_final = repo.get_run(run1.id)

    # Run 2
    run2 = await executor.run_experiment(spec)
    scores2 = await ScorerRegistry.execute_scorers_for_run(run2.id, spec, repo)
    run2_final = repo.get_run(run2.id)

    # Assert identical aggregate scores
    assert run1_final.aggregate_metrics["mean_score"] == run2_final.aggregate_metrics["mean_score"]
    assert run1_final.aggregate_metrics["pass_rate"] == run2_final.aggregate_metrics["pass_rate"]

    # Assert identical ordering and scores across all cases
    assert len(scores1) == len(scores2)
    for s1, s2 in zip(scores1, scores2):
        assert s1.case_id == s2.case_id
        assert s1.config_id == s2.config_id
        assert s1.scorer_name == s2.scorer_name
        assert s1.score == s2.score
        assert s1.band == s2.band

    await repo.aclose()

@pytest.mark.asyncio
async def test_ci_regression_fails_predictably(temp_db_path):
    """Proves that CI gate fails predictably when regression threshold is breached."""
    repo = Repository(temp_db_path)
    spec = Planner.load_experiment_spec("experiments/ci_experiment.yaml")

    executor = Executor(repo)
    run = await executor.run_experiment(spec)
    await ScorerRegistry.execute_scorers_for_run(run.id, spec, repo)

    # Gate requiring impossible 100% pass score
    strict_gate = GateConfig(min_aggregate_score=0.999)
    comp = RunComparator.compare(run.id, run.id, repo, gate_config=strict_gate)
    assert comp.gates_passed is False

    await repo.aclose()
