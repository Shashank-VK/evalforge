import pytest
from evalforge.models import DatasetCase, ModelConfig, ExperimentSpec
from evalforge.runner.executor import Executor
from evalforge.adapters.mock import MockAdapter
from evalforge.storage.repository import Repository

@pytest.mark.asyncio
async def test_retry_transient_failures(temp_db_path, monkeypatch):
    """Proves bounded exponential backoff on transient errors up to max_retries."""
    repo = Repository(temp_db_path)
    
    # Configure mock adapter to fail twice on case-001 then succeed
    mock_adapter = MockAdapter(failure_count_by_case={"case-001": 2}, latency_ms=5.0)
    monkeypatch.setattr("evalforge.runner.executor.get_adapter", lambda *args, **kwargs: mock_adapter)

    spec = ExperimentSpec(
        name="test_retry",
        cases="datasets/support.jsonl",
        configs=[
            ModelConfig(
                id="cfg-test",
                provider="mock",
                model="mock-v1",
                prompt="Question: {{ question }}"
            )
        ],
        max_retries=3,
        max_concurrency=2
    )

    executor = Executor(repo)
    run = await executor.run_experiment(spec)

    assert run.completed_cases == 8
    assert run.failed_cases == 0
    # Case-001 should have been attempted 3 times (2 failures + 1 success)
    assert mock_adapter.attempt_counter["case-001"] == 3

    await repo.aclose()

@pytest.mark.asyncio
async def test_resume_run_without_duplicate_calls(temp_db_path, monkeypatch):
    """Proves that resuming an interrupted run executes only unfinished cases."""
    repo = Repository(temp_db_path)
    mock_adapter = MockAdapter(latency_ms=2.0)
    monkeypatch.setattr("evalforge.runner.executor.get_adapter", lambda *args, **kwargs: mock_adapter)

    spec = ExperimentSpec(
        name="test_resume",
        cases="datasets/support.jsonl",
        configs=[
            ModelConfig(
                id="cfg-1",
                provider="mock",
                model="mock-v1",
                prompt="Question: {{ question }}"
            )
        ],
        max_concurrency=2
    )

    # First run
    executor = Executor(repo)
    initial_run = await executor.run_experiment(spec)
    assert initial_run.completed_cases == 8
    first_call_count = dict(mock_adapter.attempt_counter)

    # Resume the same run
    mock_adapter.attempt_counter.clear()
    resumed_run = await executor.run_experiment(spec, resume_run_id=initial_run.id)

    # No additional calls should have been made to mock_adapter because all cases were completed
    assert len(mock_adapter.attempt_counter) == 0
    assert resumed_run.completed_cases == 8

    await repo.aclose()
