import asyncio
import uuid
import pytest
from evalforge.models import CaseResult, Score, Run
from evalforge.storage.repository import Repository
from evalforge.constants import ADAPTER_VERSION, FIXTURE_VERSION, SCORER_VERSION

@pytest.mark.asyncio
async def test_concurrent_writes_no_database_lock(temp_db_path):
    """Proves that SQLite WAL mode and serialized AsyncWriterQueue prevent
    'database is locked' errors under high async concurrency.
    """
    repo = Repository(temp_db_path)
    run_id = str(uuid.uuid4())

    run = Run(
        id=run_id,
        name="concurrency_test_run",
        status="running",
        experiment_spec={},
        spec_hash="hash123",
        created_at="2026-10-10T00:00:00Z"
    )
    await repo.save_run(run)

    num_concurrent_writers = 60

    async def write_worker(idx: int):
        case_id = f"case-{idx:03d}"
        res = CaseResult(
            run_id=run_id,
            case_id=case_id,
            config_id="config-a",
            prompt_rendered=f"Prompt for case {idx}",
            prompt_hash="p_hash",
            response_text=f"Response for case {idx}",
            status="completed",
            latency_ms=15.0,
            input_tokens=20,
            output_tokens=10,
            estimated_cost_usd=0.00001,
            provider="mock",
            model="mock-v1",
            adapter_version=ADAPTER_VERSION,
            fixture_version=FIXTURE_VERSION,
            created_at="2026-10-10T00:00:00Z"
        )
        await repo.save_case_result(res)

        score = Score(
            id=str(uuid.uuid4()),
            run_id=run_id,
            case_id=case_id,
            config_id="config-a",
            scorer_name="contains",
            scorer_version=SCORER_VERSION,
            score=1.0,
            passed=True,
            band="pass",
            explanation="Parallel score write",
            details={}
        )
        await repo.save_scores([score])

    # Run 60 workers simultaneously
    tasks = [write_worker(i) for i in range(num_concurrent_writers)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Assert no exceptions occurred
    for r in results:
        assert not isinstance(r, Exception), f"Concurrent write threw exception: {r}"

    # Verify all 60 cases and scores were written accurately
    case_results = repo.get_case_results(run_id)
    assert len(case_results) == num_concurrent_writers

    scores = repo.get_scores(run_id)
    assert len(scores) == num_concurrent_writers

    await repo.aclose()
