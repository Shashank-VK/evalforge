import json
from typing import Any
from evalforge.models import Run, CaseResult, Score
from evalforge.storage.repository import Repository

class JsonReporter:
    """Exports run records, case results, and scores to structured JSON."""

    @staticmethod
    def generate_report(run_id: str, repository: Repository) -> dict[str, Any]:
        run = repository.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        case_results = repository.get_case_results(run_id)
        scores = repository.get_scores(run_id)

        # Group scores by (case_id, config_id)
        scores_by_case = {}
        for s in scores:
            key = f"{s.case_id}:{s.config_id}"
            if key not in scores_by_case:
                scores_by_case[key] = []
            scores_by_case[key].append(s.model_dump())

        results_data = []
        for r in case_results:
            key = f"{r.case_id}:{r.config_id}"
            item = r.model_dump()
            item["scores"] = scores_by_case.get(key, [])
            results_data.append(item)

        return {
            "run": run.model_dump(),
            "results": results_data,
            "aggregate_metrics": run.aggregate_metrics
        }

    @staticmethod
    def export_to_file(run_id: str, repository: Repository, output_path: str) -> None:
        data = JsonReporter.generate_report(run_id, repository)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
