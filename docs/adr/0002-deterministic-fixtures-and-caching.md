# ADR 0002: Deterministic Recorded Fixtures and Networkless CI Gate

## Status
Accepted

## Context
Running automated tests against live hosted LLM APIs in CI pipelines introduces flakiness (due to provider downtime, network latency, rate limits), security exposure (API tokens exposed to pull requests), and unbounded financial costs.

## Decision
1. Separate CI gate execution from exploratory live model benchmarking.
2. The CI pipeline (`ci.yml`) operates 100% offline using `FixtureAdapter`, which replays committed golden fixtures from `fixtures/recorded_responses.json`.
3. Pinned seeds (`seed: 42`) and pinned evaluator versions guarantee reproducible, byte-for-byte consistent evaluation scores across identical runs.
4. Exploratory runs with hosted providers are isolated in a manual workflow (`benchmark.yml`) requiring explicit approval and protected secrets.
5. In hosted runs, responses are cached by normalized request hash in SQLite `request_cache` table to prevent re-paying for identical calls.

## Consequences
- **Positive**: 100% reliable CI that never flakes due to LLM provider downtime. Zero API dollar cost on pull requests.
- **Negative**: Developing new test cases requires recording responses into the fixture catalog before merging to main.
