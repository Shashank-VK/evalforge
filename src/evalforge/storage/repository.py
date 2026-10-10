import json
import sqlite3
from typing import Optional
from evalforge.models import Run, CaseResult, Score
from evalforge.storage.db import get_connection, init_db
from evalforge.storage.queue import AsyncWriterQueue
from evalforge.logger import get_logger

logger = get_logger(__name__)

class Repository:
    """Data repository providing CRUD operations for runs, case results, and scores."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        init_db(db_path)
        self.writer_queue = AsyncWriterQueue(db_path)

    def close(self) -> None:
        pass

    async def aclose(self) -> None:
        await self.writer_queue.stop()

    # --- Runs ---

    def _sync_save_run(self, conn: sqlite3.Connection, run: Run) -> None:
        conn.execute("""
            INSERT INTO runs (
                id, name, status, stop_reason, experiment_spec, spec_hash,
                total_cases, completed_cases, failed_cases, total_cost_usd,
                spending_cap_usd, seed, created_at, completed_at, aggregate_metrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                stop_reason=excluded.stop_reason,
                completed_cases=excluded.completed_cases,
                failed_cases=excluded.failed_cases,
                total_cost_usd=excluded.total_cost_usd,
                completed_at=excluded.completed_at,
                aggregate_metrics=excluded.aggregate_metrics
        """, (
            run.id,
            run.name,
            run.status,
            run.stop_reason,
            json.dumps(run.experiment_spec),
            run.spec_hash,
            run.total_cases,
            run.completed_cases,
            run.failed_cases,
            run.total_cost_usd,
            run.spending_cap_usd,
            run.seed,
            run.created_at,
            run.completed_at,
            json.dumps(run.aggregate_metrics),
        ))

    async def save_run(self, run: Run) -> None:
        await self.writer_queue.execute_write(lambda conn: self._sync_save_run(conn, run))

    def save_run_sync(self, run: Run) -> None:
        conn = get_connection(self.db_path)
        try:
            self._sync_save_run(conn, run)
            conn.commit()
        finally:
            conn.close()

    def get_run(self, run_id: str) -> Optional[Run]:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_run(row)
        finally:
            conn.close()

    def list_runs(self) -> list[Run]:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT * FROM runs ORDER BY created_at DESC")
            return [self._row_to_run(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def _row_to_run(self, row: sqlite3.Row) -> Run:
        return Run(
            id=row["id"],
            name=row["name"],
            status=row["status"],
            stop_reason=row["stop_reason"],
            experiment_spec=json.loads(row["experiment_spec"]),
            spec_hash=row["spec_hash"],
            total_cases=row["total_cases"],
            completed_cases=row["completed_cases"],
            failed_cases=row["failed_cases"],
            total_cost_usd=row["total_cost_usd"],
            spending_cap_usd=row["spending_cap_usd"],
            seed=row["seed"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            aggregate_metrics=json.loads(row["aggregate_metrics"]),
        )

    # --- Case Results ---

    def _sync_save_case_result(self, conn: sqlite3.Connection, res: CaseResult) -> None:
        conn.execute("""
            INSERT INTO case_results (
                run_id, case_id, config_id, prompt_rendered, prompt_hash,
                response_text, status, error, latency_ms, input_tokens,
                output_tokens, estimated_cost_usd, provider, model,
                adapter_version, fixture_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, case_id, config_id) DO UPDATE SET
                response_text=excluded.response_text,
                status=excluded.status,
                error=excluded.error,
                latency_ms=excluded.latency_ms,
                input_tokens=excluded.input_tokens,
                output_tokens=excluded.output_tokens,
                estimated_cost_usd=excluded.estimated_cost_usd
        """, (
            res.run_id, res.case_id, res.config_id, res.prompt_rendered, res.prompt_hash,
            res.response_text, res.status, res.error, res.latency_ms, res.input_tokens,
            res.output_tokens, res.estimated_cost_usd, res.provider, res.model,
            res.adapter_version, res.fixture_version, res.created_at
        ))

    async def save_case_result(self, res: CaseResult) -> None:
        await self.writer_queue.execute_write(lambda conn: self._sync_save_case_result(conn, res))

    def get_case_results(self, run_id: str, config_id: Optional[str] = None) -> list[CaseResult]:
        conn = get_connection(self.db_path)
        try:
            if config_id:
                cur = conn.execute("SELECT * FROM case_results WHERE run_id = ? AND config_id = ? ORDER BY case_id", (run_id, config_id))
            else:
                cur = conn.execute("SELECT * FROM case_results WHERE run_id = ? ORDER BY case_id, config_id", (run_id,))
            return [self._row_to_case_result(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_completed_case_keys(self, run_id: str) -> set[tuple[str, str]]:
        """Returns set of (case_id, config_id) for completed cases in a run."""
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT case_id, config_id FROM case_results WHERE run_id = ? AND status = 'completed'", (run_id,))
            return {(row[0], row[1]) for row in cur.fetchall()}
        finally:
            conn.close()

    def _row_to_case_result(self, row: sqlite3.Row) -> CaseResult:
        return CaseResult(
            run_id=row["run_id"],
            case_id=row["case_id"],
            config_id=row["config_id"],
            prompt_rendered=row["prompt_rendered"],
            prompt_hash=row["prompt_hash"],
            response_text=row["response_text"],
            status=row["status"],
            error=row["error"],
            latency_ms=row["latency_ms"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            estimated_cost_usd=row["estimated_cost_usd"],
            provider=row["provider"],
            model=row["model"],
            adapter_version=row["adapter_version"],
            fixture_version=row["fixture_version"],
            created_at=row["created_at"],
        )

    # --- Scores ---

    def _sync_save_scores(self, conn: sqlite3.Connection, scores: list[Score]) -> None:
        for s in scores:
            conn.execute("""
                INSERT INTO scores (
                    id, run_id, case_id, config_id, scorer_name, scorer_version,
                    score, passed, band, explanation, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    score=excluded.score,
                    passed=excluded.passed,
                    band=excluded.band,
                    explanation=excluded.explanation,
                    details=excluded.details
            """, (
                s.id, s.run_id, s.case_id, s.config_id, s.scorer_name, s.scorer_version,
                s.score, 1 if s.passed else 0, s.band, s.explanation, json.dumps(s.details)
            ))

    async def save_scores(self, scores: list[Score]) -> None:
        await self.writer_queue.execute_write(lambda conn: self._sync_save_scores(conn, scores))

    def save_scores_sync(self, scores: list[Score]) -> None:
        conn = get_connection(self.db_path)
        try:
            self._sync_save_scores(conn, scores)
            conn.commit()
        finally:
            conn.close()

    def get_scores(self, run_id: str, config_id: Optional[str] = None) -> list[Score]:
        conn = get_connection(self.db_path)
        try:
            if config_id:
                cur = conn.execute("SELECT * FROM scores WHERE run_id = ? AND config_id = ? ORDER BY case_id, scorer_name", (run_id, config_id))
            else:
                cur = conn.execute("SELECT * FROM scores WHERE run_id = ? ORDER BY case_id, config_id, scorer_name", (run_id,))
            return [self._row_to_score(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def _row_to_score(self, row: sqlite3.Row) -> Score:
        return Score(
            id=row["id"],
            run_id=row["run_id"],
            case_id=row["case_id"],
            config_id=row["config_id"],
            scorer_name=row["scorer_name"],
            scorer_version=row["scorer_version"],
            score=row["score"],
            passed=bool(row["passed"]),
            band=row["band"],
            explanation=row["explanation"],
            details=json.loads(row["details"]),
        )

    # --- Request Cache ---

    def get_cached_response(self, request_hash: str) -> Optional[dict]:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT response_payload FROM request_cache WHERE request_hash = ?", (request_hash,))
            row = cur.fetchone()
            if not row:
                return None
            return json.loads(row[0])
        finally:
            conn.close()

    async def set_cached_response(self, request_hash: str, payload: dict) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        serialized = json.dumps(payload)
        await self.writer_queue.execute_write(
            lambda conn: conn.execute(
                "INSERT OR REPLACE INTO request_cache (request_hash, response_payload, created_at) VALUES (?, ?, ?)",
                (request_hash, serialized, now)
            )
        )

    # --- Reset & Cleanup ---

    def clear_all(self) -> None:
        """Deletes all data across runs, case results, scores, and cache."""
        conn = get_connection(self.db_path)
        try:
            conn.execute("DELETE FROM scores;")
            conn.execute("DELETE FROM case_results;")
            conn.execute("DELETE FROM runs;")
            conn.execute("DELETE FROM request_cache;")
            conn.commit()
        finally:
            conn.close()
