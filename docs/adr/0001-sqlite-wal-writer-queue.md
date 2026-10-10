# ADR 0001: SQLite WAL Mode and Serialized Async Writer Queue

## Status
Accepted

## Context
When running concurrent model evaluations (e.g. 4 to 50 concurrent async tasks), parallel write operations to SQLite can encounter `sqlite3.OperationalError: database is locked`. For a portable, developer-friendly evaluation harness, requiring an external PostgreSQL or Redis cluster introduces heavy infrastructure overhead.

## Decision
1. Enable SQLite Write-Ahead Logging (`PRAGMA journal_mode=WAL;`), `PRAGMA synchronous=NORMAL;`, and a 10-second busy timeout (`PRAGMA busy_timeout=10000;`).
2. Implement a dedicated `AsyncWriterQueue` that accepts write closures via an `asyncio.Queue` and executes them sequentially on a single dedicated connection in a dedicated task loop.

## Consequences
- **Positive**: Zero "database is locked" errors under 50+ concurrent evaluation workers. Completely portable single-file SQLite database with zero external service dependencies.
- **Negative**: High write throughput is bounded by sequential SQLite execution speed, which is more than sufficient for thousands of evaluation cases per minute.
