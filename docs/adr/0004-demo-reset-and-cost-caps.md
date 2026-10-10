# ADR 0004: Authenticated Demo Reset and Spending Caps

## Status
Accepted

## Context
Interactive demos frequently accumulate experimental artifacts, leaving dirty session states that confuse reviewers or break scripted walkthroughs. Live model evaluation without spending caps risks runaway API costs.

## Decision
1. Implement a demo-only endpoint `POST /api/demo/reset`.
   - Requires `DEMO_MODE=true` environment flag; returns HTTP 403 Forbidden in production mode.
   - Requires valid `X-Demo-Key` or `Authorization: Bearer <key>` header; returns HTTP 401 Unauthorized if invalid.
   - Wipes session data, clears report caches, and reseeds clean baseline and candidate evaluation runs.
   - Execution is strictly idempotent.
2. Introduce preflight cost estimation and a per-run spending cap (`spending_cap_usd`).
   - If accumulated cost reaches the spending cap, the executor terminates remaining tasks cleanly, labels the run `status: partial` with `stop_reason: spending_cap_exceeded`, and saves all completed checkpoints without data loss.

## Consequences
- **Positive**: Guaranteed recovery of live demos in under 30 seconds. Deterministic budget boundaries for AI runs.
- **Negative**: Runs with aggressive caps may terminate early if prices or token lengths exceed expectations.
