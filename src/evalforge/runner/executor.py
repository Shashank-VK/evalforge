import asyncio
import hashlib
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from evalforge.models import (
    Dataset,
    DatasetCase,
    ModelConfig,
    ExperimentSpec,
    Run,
    CaseResult,
    GenerationResult
)
from evalforge.constants import (
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_PARTIAL,
    STATUS_FAILED,
    STOP_REASON_COMPLETED,
    STOP_REASON_SPENDING_CAP_EXCEEDED,
    STOP_REASON_ERROR,
    ADAPTER_VERSION,
    FIXTURE_VERSION
)
from evalforge.storage.repository import Repository
from evalforge.adapters.factory import get_adapter
from evalforge.runner.planner import Planner
from evalforge.runner.cost_tracker import CostTracker
from evalforge.exceptions import ProviderError, SpendingCapExceededError
from evalforge.logger import get_logger

logger = get_logger(__name__)

class Executor:
    """Async execution engine for running evaluation experiments with bounded concurrency,
    exponential backoff retries, spending cap enforcement, and resume capabilities.
    """
    def __init__(self, repository: Repository):
        self.repository = repository

    async def run_experiment(
        self,
        spec: ExperimentSpec,
        spec_file_path: Optional[str] = None,
        max_concurrency: Optional[int] = None,
        spending_cap_usd: Optional[float] = None,
        resume_run_id: Optional[str] = None
    ) -> Run:
        base_dir = Path(spec_file_path).parent if spec_file_path else Path(".")
        dataset_path = str(Planner.resolve_file_path(spec.cases, base_dir))
        dataset = Planner.load_dataset(dataset_path)

        concurrency = max_concurrency or spec.max_concurrency
        semaphore = asyncio.Semaphore(concurrency)

        cap = spending_cap_usd if spending_cap_usd is not None else spec.spending_cap_usd
        cost_tracker = CostTracker(spending_cap_usd=cap)

        # Preflight cost estimation
        prompt_cache: dict[str, str] = {}
        def get_rendered_prompt(cfg: ModelConfig, c: DatasetCase) -> str:
            cache_key = f"{cfg.id}:{c.id}"
            if cache_key not in prompt_cache:
                raw_template = Planner.resolve_prompt_content(cfg.prompt, base_dir)
                prompt_cache[cache_key] = Planner.render_prompt(raw_template, c.input)
            return prompt_cache[cache_key]

        preflight_cost = CostTracker.estimate_preflight_cost(dataset.cases, spec.configs, get_rendered_prompt)
        logger.info("Preflight estimated cost: $%.4f (Spending cap: %s)", preflight_cost, f"${cap:.4f}" if cap else "None")

        # Handle Run record (resume or new)
        run_id = resume_run_id or str(uuid.uuid4())
        existing_completed_keys: set[tuple[str, str]] = set()

        if resume_run_id:
            existing_run = self.repository.get_run(resume_run_id)
            if not existing_run:
                raise ValueError(f"Run {resume_run_id} not found to resume")
            existing_completed_keys = self.repository.get_completed_case_keys(resume_run_id)
            run = existing_run
            run.status = STATUS_RUNNING
            logger.info("Resuming run %s: %d cases already completed", run_id, len(existing_completed_keys))
        else:
            total_items = len(dataset.cases) * len(spec.configs)
            run = Run(
                id=run_id,
                name=spec.name,
                status=STATUS_RUNNING,
                experiment_spec=spec.model_dump(),
                spec_hash=spec.spec_hash or spec.compute_hash(),
                total_cases=total_items,
                completed_cases=0,
                failed_cases=0,
                total_cost_usd=0.0,
                spending_cap_usd=cap,
                seed=spec.seed,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            await self.repository.save_run(run)

        # Instantiate adapters per config
        adapters = {cfg.id: get_adapter(cfg.provider, repository=self.repository) for cfg in spec.configs}

        # Build task list
        tasks_to_run = []
        for case in dataset.cases:
            for config in spec.configs:
                if (case.id, config.id) in existing_completed_keys:
                    continue
                rendered = get_rendered_prompt(config, case)
                p_hash = hashlib.sha256(rendered.strip().encode("utf-8")).hexdigest()[:16]
                tasks_to_run.append((case, config, rendered, p_hash))

        completed_count = len(existing_completed_keys)
        failed_count = run.failed_cases
        stop_reason = STOP_REASON_COMPLETED
        cap_exceeded_flag = False

        async def execute_single(case: DatasetCase, config: ModelConfig, prompt_rendered: str, prompt_hash: str):
            nonlocal completed_count, failed_count, cap_exceeded_flag, stop_reason
            if cap_exceeded_flag:
                return

            adapter = adapters[config.id]
            max_retries = spec.max_retries
            attempt = 0
            gen_res: Optional[GenerationResult] = None
            last_error: Optional[str] = None

            async with semaphore:
                if cost_tracker.is_cap_exceeded():
                    cap_exceeded_flag = True
                    stop_reason = STOP_REASON_SPENDING_CAP_EXCEEDED
                    return

                while attempt <= max_retries:
                    try:
                        gen_res = await adapter.generate(
                            prompt=prompt_rendered,
                            case=case,
                            config=config,
                            seed=spec.seed
                        )
                        break
                    except ProviderError as pe:
                        last_error = str(pe)
                        if pe.retryable and attempt < max_retries:
                            backoff = (2 ** attempt) * 0.2
                            logger.warning("Retryable error on case %s (attempt %d/%d): %s. Backing off %.2fs",
                                           case.id, attempt + 1, max_retries, pe, backoff)
                            await asyncio.sleep(backoff)
                            attempt += 1
                        else:
                            break
                    except Exception as ex:
                        last_error = str(ex)
                        break

            now_str = datetime.now(timezone.utc).isoformat()
            if gen_res and not gen_res.error:
                cost_tracker.add_cost(gen_res.estimated_cost_usd)
                case_result = CaseResult(
                    run_id=run_id,
                    case_id=case.id,
                    config_id=config.id,
                    prompt_rendered=prompt_rendered,
                    prompt_hash=prompt_hash,
                    response_text=gen_res.response_text,
                    status="completed",
                    latency_ms=gen_res.latency_ms,
                    input_tokens=gen_res.input_tokens,
                    output_tokens=gen_res.output_tokens,
                    estimated_cost_usd=gen_res.estimated_cost_usd,
                    provider=config.provider,
                    model=config.model,
                    adapter_version=ADAPTER_VERSION,
                    fixture_version=FIXTURE_VERSION,
                    created_at=now_str
                )
                completed_count += 1
            else:
                err_msg = gen_res.error if (gen_res and gen_res.error) else (last_error or "Unknown failure")
                case_result = CaseResult(
                    run_id=run_id,
                    case_id=case.id,
                    config_id=config.id,
                    prompt_rendered=prompt_rendered,
                    prompt_hash=prompt_hash,
                    response_text="",
                    status="failed",
                    error=err_msg,
                    provider=config.provider,
                    model=config.model,
                    adapter_version=ADAPTER_VERSION,
                    fixture_version=FIXTURE_VERSION,
                    created_at=now_str
                )
                failed_count += 1

            # Checkpoint immediately to SQLite via writer queue
            await self.repository.save_case_result(case_result)

            # Check spending cap after adding result
            if cost_tracker.is_cap_exceeded():
                cap_exceeded_flag = True
                stop_reason = STOP_REASON_SPENDING_CAP_EXCEEDED
                logger.warning("Spending cap reached ($%.4f >= $%.4f). Halting remaining cases.",
                               cost_tracker.accumulated_cost_usd, cap)

        # Run tasks with concurrency
        eval_tasks = [execute_single(*item) for item in tasks_to_run]
        if eval_tasks:
            await asyncio.gather(*eval_tasks, return_exceptions=True)

        # Update run status
        final_status = STATUS_COMPLETED
        if cap_exceeded_flag:
            final_status = STATUS_PARTIAL
        elif failed_count > 0 and completed_count == 0:
            final_status = STATUS_FAILED
            stop_reason = STOP_REASON_ERROR

        run.status = final_status
        run.stop_reason = stop_reason
        run.completed_cases = completed_count
        run.failed_cases = failed_count
        run.total_cost_usd = round(cost_tracker.accumulated_cost_usd, 6)
        run.completed_at = datetime.now(timezone.utc).isoformat()

        await self.repository.save_run(run)
        logger.info("Run %s finished with status '%s' (%d completed, %d failed, total cost $%.4f)",
                    run.id, run.status, run.completed_cases, run.failed_cases, run.total_cost_usd)
        return run
