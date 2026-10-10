import pytest
from evalforge.models import ExperimentSpec, ModelConfig, GenerationResult
from evalforge.runner.executor import Executor
from evalforge.runner.cost_tracker import CostTracker
from evalforge.adapters.base import ProviderAdapter
from evalforge.storage.repository import Repository
from evalforge.constants import STATUS_PARTIAL, STOP_REASON_SPENDING_CAP_EXCEEDED

class ExpensiveMockAdapter(ProviderAdapter):
    """Adapter that simulates charges of $0.50 per call."""
    async def generate(self, prompt, case, config, seed=42):
        return GenerationResult(
            response_text="Expensive response",
            input_tokens=1000,
            output_tokens=1000,
            latency_ms=10.0,
            estimated_cost_usd=0.50
        )

@pytest.mark.asyncio
async def test_spending_cap_stops_cleanly_and_labels_partial(temp_db_path, monkeypatch):
    """Proves that exceeding spending cap stops cleanly and labels the run partial."""
    repo = Repository(temp_db_path)
    expensive_adapter = ExpensiveMockAdapter()
    monkeypatch.setattr("evalforge.runner.executor.get_adapter", lambda *args, **kwargs: expensive_adapter)

    # 8 cases in dataset, at $0.50 each = $4.00 total.
    # Set spending cap at $1.00 so it must stop after ~2 cases.
    spec = ExperimentSpec(
        name="test_spending_cap",
        cases="datasets/support.jsonl",
        configs=[
            ModelConfig(
                id="cfg-expensive",
                provider="mock",
                model="gpt-4o",
                prompt="Question: {{ question }}"
            )
        ],
        spending_cap_usd=1.00,
        max_concurrency=1
    )

    executor = Executor(repo)
    run = await executor.run_experiment(spec)

    assert run.status == STATUS_PARTIAL
    assert run.stop_reason == STOP_REASON_SPENDING_CAP_EXCEEDED
    assert run.completed_cases < 8
    assert run.total_cost_usd >= 1.00
    assert run.total_cost_usd <= 1.50

    await repo.aclose()
