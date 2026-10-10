import asyncio
import os
from pathlib import Path
from evalforge.models import ExperimentSpec
from evalforge.storage.repository import Repository
from evalforge.runner.planner import Planner
from evalforge.runner.executor import Executor
from evalforge.scorers.registry import ScorerRegistry
from evalforge.logger import get_logger

logger = get_logger(__name__)

def seed_demo_data(repository: Repository) -> list[str]:
    """Deterministically runs and scores sample suites, returning list of seeded run IDs."""
    pkg_dir = Path(__file__).resolve().parent
    # Project root is parent of src or relative to cwd
    candidates = [
        pkg_dir.parent.parent,
        Path.cwd(),
        Path("/home/hatch/workspace/goals/land-a-ds-ml-internship-or-job/builds/evalforge")
    ]
    project_root = candidates[0]
    for c in candidates:
        if (c / "experiments" / "support_eval.yaml").exists():
            project_root = c
            break

    spec_path = str(project_root / "experiments" / "support_eval.yaml")
    spec = Planner.load_experiment_spec(spec_path)
    executor = Executor(repository)

    async def _run_and_score():
        # 1. Run baseline-only
        baseline_spec = spec.model_copy(deep=True)
        baseline_spec.name = "support_baseline_prompt_v1"
        baseline_spec.configs = [c for c in spec.configs if c.id == "baseline"]
        run_baseline = await executor.run_experiment(
            spec=baseline_spec,
            spec_file_path=spec_path
        )
        await ScorerRegistry.execute_scorers_for_run(
            run_id=run_baseline.id,
            spec=baseline_spec,
            repository=repository,
            base_dir=project_root / "experiments"
        )

        # 2. Run candidate-only
        candidate_spec = spec.model_copy(deep=True)
        candidate_spec.name = "support_candidate_prompt_v2"
        candidate_spec.configs = [c for c in spec.configs if c.id == "candidate"]
        run_candidate = await executor.run_experiment(
            spec=candidate_spec,
            spec_file_path=spec_path
        )
        await ScorerRegistry.execute_scorers_for_run(
            run_id=run_candidate.id,
            spec=candidate_spec,
            repository=repository,
            base_dir=project_root / "experiments"
        )

        await repository.aclose()
        return [run_baseline.id, run_candidate.id]

    run_ids = asyncio.run(_run_and_score())
    logger.info("Successfully seeded demo runs: %s", run_ids)
    return run_ids
