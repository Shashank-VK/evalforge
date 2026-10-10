import os
from typing import Any, Union
from pathlib import Path
from evalforge.scorers.base import BaseScorer
from evalforge.scorers.exact_match import ExactMatchScorer
from evalforge.scorers.contains import ContainsScorer
from evalforge.scorers.json_schema import JsonSchemaScorer
from evalforge.scorers.semantic import SemanticSimilarityScorer
from evalforge.scorers.citation import CitationScorer
from evalforge.scorers.rubric import RubricJudgeScorer
from evalforge.models import DatasetCase, CaseResult, Score, ExperimentSpec, Run
from evalforge.storage.repository import Repository
from evalforge.runner.planner import Planner
from evalforge.constants import PASS_BAND_PASS, PASS_BAND_NEEDS_REVIEW, PASS_BAND_FAIL
from evalforge.logger import get_logger

logger = get_logger(__name__)

class ScorerRegistry:
    """Registry for instantiating and executing scorers."""

    @staticmethod
    def get_scorer(declaration: Union[str, dict[str, Any]], base_dir: Path = Path(".")) -> BaseScorer:
        if isinstance(declaration, str):
            decl = declaration.strip()
            if decl.startswith("rubric:"):
                rubric_rel = decl.split(":", 1)[1].strip()
                path = str(base_dir / rubric_rel if not Path(rubric_rel).is_absolute() else rubric_rel)
                return RubricJudgeScorer(rubric_path=path)
            elif decl == "exact_match":
                return ExactMatchScorer()
            elif decl in ("contains", "facts", "safety"):
                return ContainsScorer()
            elif decl == "json_schema":
                return JsonSchemaScorer()
            elif decl in ("semantic", "semantic_similarity"):
                return SemanticSimilarityScorer()
            elif decl in ("citation", "citations"):
                return CitationScorer()
            elif decl == "rubric":
                return RubricJudgeScorer()
            else:
                logger.warning("Unrecognized scorer name '%s', defaulting to ContainsScorer", decl)
                return ContainsScorer()
        elif isinstance(declaration, dict):
            if "rubric" in declaration:
                rubric_rel = declaration["rubric"]
                path = str(base_dir / rubric_rel if not Path(rubric_rel).is_absolute() else rubric_rel)
                return RubricJudgeScorer(rubric_path=path)
            name = declaration.get("name", "contains")
            return ScorerRegistry.get_scorer(name, base_dir=base_dir)
        return ContainsScorer()

    @staticmethod
    async def execute_scorers_for_run(
        run_id: str,
        spec: ExperimentSpec,
        repository: Repository,
        specific_scorer_name: str | None = None,
        base_dir: Path = Path(".")
    ) -> list[Score]:
        """Scores all completed case results for a run and persists the scores and metrics."""
        # Load dataset cases
        dataset_path = str(Planner.resolve_file_path(spec.cases, base_dir))
        dataset = Planner.load_dataset(dataset_path)
        case_map = {c.id: c for c in dataset.cases}

        # Retrieve completed case results
        results = repository.get_case_results(run_id)
        if not results:
            logger.warning("No case results found for run %s", run_id)
            return []

        # Instantiate scorers
        scorers: list[BaseScorer] = []
        if specific_scorer_name:
            scorers.append(ScorerRegistry.get_scorer(specific_scorer_name, base_dir=base_dir))
        else:
            scorer_decls = spec.scorers or ["contains", "semantic_similarity"]
            for decl in scorer_decls:
                scorers.append(ScorerRegistry.get_scorer(decl, base_dir=base_dir))

        all_scores: list[Score] = []
        for res in results:
            if res.status != "completed":
                continue
            case = case_map.get(res.case_id)
            if not case:
                continue
            for scorer in scorers:
                score = scorer.score_case(case, res)
                all_scores.append(score)

        # Save scores via repository
        if all_scores:
            await repository.save_scores(all_scores)

        # Compute aggregate metrics
        run = repository.get_run(run_id)
        if run:
            metrics = ScorerRegistry.compute_aggregate_metrics(results, all_scores)
            run.aggregate_metrics = metrics
            await repository.save_run(run)

        return all_scores

    @staticmethod
    def compute_aggregate_metrics(results: list[CaseResult], scores: list[Score]) -> dict[str, Any]:
        """Calculates statistical metrics, pass rates, latency distributions, and costs."""
        completed_res = [r for r in results if r.status == "completed"]
        latencies = sorted([r.latency_ms for r in completed_res])

        p50_latency = latencies[len(latencies) // 2] if latencies else 0.0
        p95_index = int(len(latencies) * 0.95) if latencies else 0
        p95_latency = latencies[p95_index] if latencies else 0.0

        total_input_toks = sum(r.input_tokens for r in completed_res)
        total_output_toks = sum(r.output_tokens for r in completed_res)
        total_cost = sum(r.estimated_cost_usd for r in completed_res)

        score_values = [s.score for s in scores]
        mean_score = round(sum(score_values) / len(score_values), 4) if score_values else 0.0

        pass_count = sum(1 for s in scores if s.band == PASS_BAND_PASS)
        needs_review_count = sum(1 for s in scores if s.band == PASS_BAND_NEEDS_REVIEW)
        fail_count = sum(1 for s in scores if s.band == PASS_BAND_FAIL)
        total_scores = len(scores)

        pass_rate = round(pass_count / total_scores, 4) if total_scores else 0.0
        needs_review_rate = round(needs_review_count / total_scores, 4) if total_scores else 0.0
        fail_rate = round(fail_count / total_scores, 4) if total_scores else 0.0

        # Group by scorer
        scorer_stats = {}
        for s in scores:
            if s.scorer_name not in scorer_stats:
                scorer_stats[s.scorer_name] = []
            scorer_stats[s.scorer_name].append(s.score)

        scorer_breakdown = {
            name: {
                "mean_score": round(sum(vals) / len(vals), 4),
                "count": len(vals)
            }
            for name, vals in scorer_stats.items()
        }

        return {
            "mean_score": mean_score,
            "pass_rate": pass_rate,
            "needs_review_rate": needs_review_rate,
            "fail_rate": fail_rate,
            "latency_p50_ms": round(p50_latency, 2),
            "latency_p95_ms": round(p95_latency, 2),
            "total_input_tokens": total_input_toks,
            "total_output_tokens": total_output_toks,
            "total_tokens": total_input_toks + total_output_toks,
            "total_cost_usd": round(total_cost, 6),
            "scorer_breakdown": scorer_breakdown,
            "total_evaluations": total_scores,
            "completed_cases": len(completed_res)
        }
