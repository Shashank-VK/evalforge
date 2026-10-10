import asyncio
import os
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console

from evalforge.models import GateConfig
from evalforge.config import get_settings
from evalforge.storage.repository import Repository
from evalforge.runner.planner import Planner
from evalforge.runner.executor import Executor
from evalforge.scorers.registry import ScorerRegistry
from evalforge.comparison.comparator import RunComparator
from evalforge.comparison.gates import GateEvaluator
from evalforge.reporting.console_reporter import ConsoleReporter
from evalforge.reporting.html_reporter import HtmlReporter
from evalforge.reporting.json_reporter import JsonReporter
from evalforge.exceptions import ValidationFailedError, GateFailureError

app = typer.Typer(help="EvalForge: Provider-agnostic LLM evaluation harness.")
console = Console()

def get_repo() -> Repository:
    settings = get_settings()
    return Repository(settings.db_path)

@app.command()
def validate(spec_path: str = typer.Argument(..., help="Path to experiment YAML specification")):
    """Validates an experiment specification, prompts, and dataset cases."""
    try:
        spec = Planner.load_experiment_spec(spec_path)
        base_dir = Path(spec_path).parent
        dataset_path = str(Planner.resolve_file_path(spec.cases, base_dir))
        dataset = Planner.load_dataset(dataset_path)

        console.print(f"[bold green]✔ Specification is valid![/bold green]")
        console.print(f"  • Name: [cyan]{spec.name}[/cyan]")
        console.print(f"  • Spec Hash: [yellow]{spec.spec_hash}[/yellow]")
        console.print(f"  • Dataset: {dataset.name} ({len(dataset.cases)} valid cases, hash: {dataset.content_hash})")
        console.print(f"  • Configurations: {len(spec.configs)}")
        for cfg in spec.configs:
            console.print(f"    - [{cfg.id}] provider={cfg.provider}, model={cfg.model}, config_hash={cfg.config_hash}")
        console.print(f"  • Scorers: {spec.scorers}")
    except ValidationFailedError as ve:
        console.print(f"[bold red]Validation Error:[/bold red] {ve}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        raise typer.Exit(code=1)

@app.command()
def run(
    spec_path: str = typer.Argument(..., help="Path to experiment YAML"),
    max_concurrency: Optional[int] = typer.Option(None, "--max-concurrency", "-c", help="Max parallel requests"),
    spending_cap: Optional[float] = typer.Option(None, "--spending-cap", help="Spending cap in USD"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed override"),
    no_score: bool = typer.Option(False, "--no-score", help="Skip automatic scoring after run")
):
    """Executes an evaluation run from an experiment specification."""
    repo = get_repo()
    try:
        spec = Planner.load_experiment_spec(spec_path)
        if seed is not None:
            spec.seed = seed

        executor = Executor(repo)

        async def _execute():
            base_dir = Path(spec_path).parent
            run_record = await executor.run_experiment(
                spec=spec,
                spec_file_path=spec_path,
                max_concurrency=max_concurrency,
                spending_cap_usd=spending_cap
            )

            if not no_score and run_record.completed_cases > 0:
                console.print("\n[dim]Applying evaluation scorers...[/dim]")
                await ScorerRegistry.execute_scorers_for_run(
                    run_id=run_record.id,
                    spec=spec,
                    repository=repo,
                    base_dir=base_dir
                )
                run_record = repo.get_run(run_record.id)

            await repo.aclose()
            return run_record

        run_res = asyncio.run(_execute())
        ConsoleReporter.print_run_summary(run_res)

        console.print(f"\n[green]Run completed![/green] Run ID: [bold]{run_res.id}[/bold]")
        console.print(f"Export report: [dim]evalforge export {run_res.id} --format html[/dim]")

    except Exception as e:
        console.print(f"[bold red]Execution Error:[/bold red] {e}")
        raise typer.Exit(code=1)

@app.command()
def resume(run_id: str = typer.Argument(..., help="ID of the interrupted run to resume")):
    """Resumes an interrupted or partial run without duplicating completed cases."""
    repo = get_repo()
    run_record = repo.get_run(run_id)
    if not run_record:
        console.print(f"[bold red]Error:[/bold red] Run {run_id} not found")
        raise typer.Exit(code=1)

    try:
        from evalforge.models import ExperimentSpec
        spec = ExperimentSpec(**run_record.experiment_spec)
        executor = Executor(repo)

        async def _resume():
            res = await executor.run_experiment(
                spec=spec,
                resume_run_id=run_id
            )
            console.print("\n[dim]Scoring updated results...[/dim]")
            await ScorerRegistry.execute_scorers_for_run(
                run_id=res.id,
                spec=spec,
                repository=repo
            )
            await repo.aclose()
            return repo.get_run(res.id)

        updated_run = asyncio.run(_resume())
        ConsoleReporter.print_run_summary(updated_run)
        console.print(f"\n[bold green]Run resumed and finalized![/bold green] ID: {updated_run.id}")

    except Exception as e:
        console.print(f"[bold red]Resume Error:[/bold red] {e}")
        raise typer.Exit(code=1)

@app.command()
def score(
    run_id: str = typer.Argument(..., help="Run ID to score"),
    scorer: Optional[str] = typer.Option(None, "--scorer", "-s", help="Specific scorer name")
):
    """Scores an existing run's raw outputs without re-calling models."""
    repo = get_repo()
    run_record = repo.get_run(run_id)
    if not run_record:
        console.print(f"[bold red]Error:[/bold red] Run {run_id} not found")
        raise typer.Exit(code=1)

    try:
        from evalforge.models import ExperimentSpec
        spec = ExperimentSpec(**run_record.experiment_spec)

        async def _score():
            scores = await ScorerRegistry.execute_scorers_for_run(
                run_id=run_id,
                spec=spec,
                repository=repo,
                specific_scorer_name=scorer
            )
            await repo.aclose()
            return scores

        scores = asyncio.run(_score())
        console.print(f"[bold green]Computed {len(scores)} evaluation score(s)![/bold green]")
        updated = repo.get_run(run_id)
        if updated:
            ConsoleReporter.print_run_summary(updated)

    except Exception as e:
        console.print(f"[bold red]Scoring Error:[/bold red] {e}")
        raise typer.Exit(code=1)

@app.command()
def compare(
    baseline_id: str = typer.Argument(..., help="Baseline run ID"),
    candidate_id: str = typer.Argument(..., help="Candidate run ID"),
    gate: Optional[str] = typer.Option(None, "--gate", "-g", help="Path to gates.yaml config")
):
    """Compares baseline and candidate runs, computes deltas, and validates CI gates."""
    repo = get_repo()
    try:
        gate_config = GateEvaluator.load_gate_config(gate) if gate else None
        comparison = RunComparator.compare(baseline_id, candidate_id, repo, gate_config=gate_config)
        ConsoleReporter.print_comparison(comparison)

        if gate and not comparison.gates_passed:
            console.print("\n[bold red]CI GATE FAILURE: Candidate failed one or more regression thresholds![/bold red]")
            raise typer.Exit(code=1)
        elif gate:
            console.print("\n[bold green]CI GATE PASSED: All regression criteria satisfied.[/bold green]")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Comparison Error:[/bold red] {e}")
        raise typer.Exit(code=1)

@app.command()
def export(
    run_id: str = typer.Argument(..., help="Run ID to export"),
    format: str = typer.Option("html", "--format", "-f", help="Export format: html or json"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (default: report.<ext>)")
):
    """Exports run results, metrics, and case drill-downs to HTML or JSON."""
    repo = get_repo()
    try:
        out_path = output or f"report_{run_id[:8]}.{format}"
        if format.lower() == "html":
            HtmlReporter.export_to_file(run_id, repo, out_path)
            console.print(f"[bold green]HTML report exported to:[/bold green] [cyan]{out_path}[/cyan]")
        elif format.lower() == "json":
            JsonReporter.export_to_file(run_id, repo, out_path)
            console.print(f"[bold green]JSON report exported to:[/bold green] [cyan]{out_path}[/cyan]")
        else:
            console.print(f"[bold red]Unsupported format:[/bold red] {format}. Choose 'html' or 'json'.")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Export Error:[/bold red] {e}")
        raise typer.Exit(code=1)

@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host interface"),
    port: int = typer.Option(8000, "--port", "-p", help="Port number")
):
    """Starts the EvalForge web dashboard and API server."""
    import uvicorn
    console.print(f"[bold green]Starting EvalForge server on http://{host}:{port}...[/bold green]")
    uvicorn.run("evalforge.server.app:app", host=host, port=port, reload=False)

@app.command()
def demo_reset(
    key: Optional[str] = typer.Option(None, "--key", "-k", help="Demo admin key override")
):
    """CLI trigger for authenticated demo reset."""
    settings = get_settings()
    admin_key = key or settings.demo_admin_key
    if not settings.demo_mode:
        console.print("[bold red]Error:[/bold red] Demo reset is disabled outside demo mode (DEMO_MODE=false)")
        raise typer.Exit(code=1)

    repo = get_repo()
    repo.clear_all()
    from evalforge.seed import seed_demo_data
    seeded = seed_demo_data(repo)
    console.print(f"[bold green]Demo reset complete![/bold green] Seeded {len(seeded)} runs.")
