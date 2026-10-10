import sqlite3
import os
from pathlib import Path
from evalforge.logger import get_logger

logger = get_logger(__name__)

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=10000;

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    stop_reason TEXT,
    experiment_spec TEXT NOT NULL,
    spec_hash TEXT NOT NULL,
    total_cases INTEGER NOT NULL DEFAULT 0,
    completed_cases INTEGER NOT NULL DEFAULT 0,
    failed_cases INTEGER NOT NULL DEFAULT 0,
    total_cost_usd REAL NOT NULL DEFAULT 0.0,
    spending_cap_usd REAL,
    seed INTEGER NOT NULL DEFAULT 42,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    aggregate_metrics TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS case_results (
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    prompt_rendered TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    response_text TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    latency_ms REAL NOT NULL DEFAULT 0.0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    fixture_version TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, case_id, config_id),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scores (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    scorer_name TEXT NOT NULL,
    scorer_version TEXT NOT NULL,
    score REAL NOT NULL,
    passed INTEGER NOT NULL,
    band TEXT NOT NULL,
    explanation TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS request_cache (
    request_hash TEXT PRIMARY KEY,
    response_payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_case_results_run ON case_results(run_id);
CREATE INDEX IF NOT EXISTS idx_scores_run ON scores(run_id);
CREATE INDEX IF NOT EXISTS idx_scores_run_case ON scores(run_id, case_id, config_id);
"""

def get_connection(db_path: str) -> sqlite3.Connection:
    """Returns a SQLite connection configured with WAL and busy timeout."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db(db_path: str) -> None:
    """Initializes tables and WAL configuration in the SQLite database."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
