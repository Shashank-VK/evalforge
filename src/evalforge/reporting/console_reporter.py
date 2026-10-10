from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from evalforge.models import Run, ComparisonResult

console = Console()

class ConsoleReporter:
    """Renders formatted tables, panels, and summaries using Rich."""

    @staticmethod
    def print_run_summary(run: Run) -> None:
        metrics = run.aggregate_metrics or {}
        mean_score = metrics.get("mean_score", 0.0)
        pass_rate = metrics.get("pass_rate", 0.0)
        p50 = metrics.get("latency_p50_ms", 0.0)
        p95 = metrics.get("latency_p95_ms", 0.0)

        panel_content = (
            f"[bold]Run ID:[/bold] {run.id}\n"
            f"[bold]Experiment:[/bold] {run.name}\n"
            f"[bold]Status:[/bold] [{'green' if run.status == 'completed' else 'yellow'}]{run.status}[/]\n"
            f"[bold]Stop Reason:[/bold] {run.stop_reason or 'none'}\n"
            f"[bold]Cases:[/bold] {run.completed_cases}/{run.total_cases} completed ({run.failed_cases} failed)\n"
            f"[bold]Total Cost:[/bold] ${run.total_cost_usd:.6f}\n"
            f"[bold]Aggregate Score:[/bold] [cyan]{mean_score:.4f}[/cyan] (Pass Rate: [green]{pass_rate:.1%}[/green])\n"
            f"[bold]Latency:[/bold] p50={p50:.1f}ms | p95={p95:.1f}ms"
        )
        console.print(Panel(panel_content, title="[bold blue]EvalForge Run Summary[/bold blue]", expand=False))

        breakdown = metrics.get("scorer_breakdown", {})
        if breakdown:
            table = Table(title="Scorer Breakdown", show_header=True, header_style="bold magenta")
            table.add_column("Scorer", style="dim")
            table.add_column("Mean Score", justify="right")
            table.add_column("Evaluations", justify="right")

            for name, stats in breakdown.items():
                table.add_row(name, f"{stats['mean_score']:.4f}", str(stats["count"]))
            console.print(table)

    @staticmethod
    def print_comparison(result: ComparisonResult) -> None:
        panel_content = (
            f"[bold]Baseline:[/bold] {result.baseline_name} ({result.baseline_run_id[:8]})\n"
            f"[bold]Candidate:[/bold] {result.candidate_name} ({result.candidate_run_id[:8]})\n\n"
            f"[bold]Quality Delta:[/bold] [{'green' if result.quality_delta >= 0 else 'red'}]{result.quality_delta:+.4f}[/]\n"
            f"[bold]Latency p50 Delta:[/bold] [{'green' if result.latency_p50_delta_ms <= 0 else 'yellow'}]{result.latency_p50_delta_ms:+.1f}ms[/]\n"
            f"[bold]Cost Delta:[/bold] [{'green' if result.cost_delta_usd <= 0 else 'yellow'}]${result.cost_delta_usd:+.6f}[/]\n"
            f"[bold]Regressions:[/bold] [{'red' if result.regressions else 'green'}]{len(result.regressions)} detected[/]\n"
            f"[bold]Improvements:[/bold] [green]{len(result.improvements)} detected[/]"
        )
        console.print(Panel(panel_content, title="[bold blue]Run Comparison & Trade-Offs[/bold blue]", expand=False))

        if result.gate_evaluations:
            gate_table = Table(title="CI Regression Gates", show_header=True, header_style="bold cyan")
            gate_table.add_column("Gate Rule")
            gate_table.add_column("Threshold", justify="right")
            gate_table.add_column("Actual", justify="right")
            gate_table.add_column("Status", justify="center")

            for ge in result.gate_evaluations:
                status_str = "[bold green]PASS[/bold green]" if ge.passed else "[bold red]FAIL[/bold red]"
                gate_table.add_row(ge.rule_name, str(ge.threshold), str(ge.actual_value), status_str)
            console.print(gate_table)
