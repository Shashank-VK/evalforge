"""Constants and pricing configurations for EvalForge."""

# Model pricing in USD per 1M tokens (input, output)
MODEL_PRICING = {
    "deterministic-v1": {"input_per_1m": 0.0, "output_per_1m": 0.0},
    "mock-v1": {"input_per_1m": 0.0, "output_per_1m": 0.0},
    "fixture-v1": {"input_per_1m": 0.0, "output_per_1m": 0.0},
    "gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.60},
    "gpt-4o": {"input_per_1m": 5.00, "output_per_1m": 15.00},
    "claude-3-5-sonnet": {"input_per_1m": 3.00, "output_per_1m": 15.00},
    "claude-3-haiku": {"input_per_1m": 0.25, "output_per_1m": 1.25},
}

# Default pass bands for rubric and tolerant scorers
PASS_BAND_PASS = "pass"
PASS_BAND_NEEDS_REVIEW = "needs_review"
PASS_BAND_FAIL = "fail"

THRESHOLD_PASS = 0.75
THRESHOLD_NEEDS_REVIEW = 0.50

# Run statuses
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"

# Stop reasons
STOP_REASON_COMPLETED = "completed"
STOP_REASON_SPENDING_CAP_EXCEEDED = "spending_cap_exceeded"
STOP_REASON_INTERRUPTED = "interrupted"
STOP_REASON_ERROR = "error"

# Adapter and Scorer versions
ADAPTER_VERSION = "1.0.0"
SCORER_VERSION = "1.0.0"
FIXTURE_VERSION = "2026.10.10"
