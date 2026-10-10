import pytest
from evalforge.models import Run, CaseResult, Score
from evalforge.storage.repository import Repository
from evalforge.reporting.html_reporter import HtmlReporter

@pytest.mark.asyncio
async def test_html_report_generation(temp_db_path):
    repo = Repository(temp_db_path)
    run_id = "test-html-run"

    run = Run(
        id=run_id,
        name="test_report_experiment",
        status="completed",
        experiment_spec={"name": "test"},
        spec_hash="spec123",
        completed_cases=1,
        total_cases=1,
        total_cost_usd=0.00005,
        created_at="2026-10-10T00:00:00Z",
        aggregate_metrics={
            "mean_score": 0.95,
            "pass_rate": 1.0,
            "latency_p50_ms": 20.0,
            "latency_p95_ms": 25.0,
            "scorer_breakdown": {"contains": {"mean_score": 0.95, "count": 1}}
        }
    )
    await repo.save_run(run)

    res = CaseResult(
        run_id=run_id,
        case_id="case-001",
        config_id="cfg-1",
        prompt_rendered="What is the refund window?",
        prompt_hash="p1",
        response_text="14 days full refund.",
        status="completed",
        provider="fixture",
        model="fixture-v1",
        created_at="2026-10-10T00:00:00Z"
    )
    await repo.save_case_result(res)

    score = Score(
        id="s1",
        run_id=run_id,
        case_id="case-001",
        config_id="cfg-1",
        scorer_name="contains",
        score=1.0,
        passed=True,
        band="pass",
        explanation="Matched all required criteria"
    )
    await repo.save_scores([score])

    html = HtmlReporter.generate_html(run_id, repo)
    assert "<!DOCTYPE html>" in html
    assert "EvalForge Execution Report" in html
    assert "test_report_experiment" in html
    assert "0.9500" in html
    assert "case-001" in html
    assert "Matched all required criteria" in html

    await repo.aclose()
