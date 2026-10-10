from __future__ import annotations
import hashlib
import json
from typing import Any, Optional, Union
from pydantic import BaseModel, Field, field_validator
from evalforge.constants import (
    ADAPTER_VERSION,
    SCORER_VERSION,
    STATUS_PENDING,
    STOP_REASON_COMPLETED,
    PASS_BAND_PASS,
    PASS_BAND_NEEDS_REVIEW,
    PASS_BAND_FAIL,
    THRESHOLD_PASS,
    THRESHOLD_NEEDS_REVIEW,
)

class DatasetCase(BaseModel):
    """A single evaluation case in a dataset."""
    id: str = Field(..., description="Unique case identifier within dataset")
    input: dict[str, Any] = Field(..., description="Input variables mapping to prompt templates")
    expected: Optional[dict[str, Any]] = Field(default=None, description="Ground truth expectations and constraints")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary case metadata")

    def content_hash(self) -> str:
        payload = json.dumps({"id": self.id, "input": self.input, "expected": self.expected}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

class Dataset(BaseModel):
    """Collection of dataset cases."""
    name: str
    version: str = "1.0.0"
    content_hash: str
    cases: list[DatasetCase]

class ModelConfig(BaseModel):
    """Execution configuration for an AI model/prompt."""
    id: str
    provider: str = Field(..., description="Provider: mock, fixture, openai, etc.")
    model: str = Field(..., description="Model identifier")
    prompt: str = Field(..., description="Path to prompt file or prompt template text")
    temperature: float = Field(default=0.0)
    max_tokens: int = Field(default=1024)
    parameters: dict[str, Any] = Field(default_factory=dict)
    config_hash: Optional[str] = Field(default=None)

    def compute_hash(self, prompt_content: str) -> str:
        payload = json.dumps({
            "provider": self.provider,
            "model": self.model,
            "prompt": prompt_content,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "parameters": self.parameters
        }, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

class ExperimentSpec(BaseModel):
    """Complete specification of an evaluation experiment."""
    name: str
    cases: str = Field(..., description="Path to dataset JSONL")
    configs: list[ModelConfig]
    scorers: list[Union[str, dict[str, Any]]] = Field(default_factory=list)
    spending_cap_usd: Optional[float] = Field(default=None)
    max_concurrency: int = Field(default=4, ge=1)
    max_retries: int = Field(default=3, ge=0)
    seed: int = Field(default=42)
    metadata: dict[str, Any] = Field(default_factory=dict)
    spec_hash: Optional[str] = Field(default=None)

    def compute_hash(self) -> str:
        payload = json.dumps({
            "name": self.name,
            "cases": self.cases,
            "configs": [c.model_dump(exclude={"config_hash"}) for c in self.configs],
            "scorers": self.scorers,
            "spending_cap_usd": self.spending_cap_usd,
            "seed": self.seed
        }, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

class GenerationResult(BaseModel):
    """Low-level result of a provider adapter generation call."""
    response_text: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    error: Optional[str] = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

class CaseResult(BaseModel):
    """Persisted execution result for a single case under a specific config."""
    run_id: str
    case_id: str
    config_id: str
    prompt_rendered: str
    prompt_hash: str
    response_text: str
    status: str = "completed"
    error: Optional[str] = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    provider: str
    model: str
    adapter_version: str = ADAPTER_VERSION
    fixture_version: Optional[str] = None
    created_at: str

class Score(BaseModel):
    """Score produced by an evaluator on a CaseResult."""
    id: str
    run_id: str
    case_id: str
    config_id: str
    scorer_name: str
    scorer_version: str = SCORER_VERSION
    score: float = Field(..., ge=0.0, le=1.0)
    passed: bool
    band: str = PASS_BAND_PASS  # pass, needs_review, fail
    explanation: str = Field(default="", description="Detailed rationale explaining the score")
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("band", mode="before")
    def compute_band(cls, v: Any, info: Any) -> str:
        if v in (PASS_BAND_PASS, PASS_BAND_NEEDS_REVIEW, PASS_BAND_FAIL):
            return str(v)
        return PASS_BAND_PASS

    @classmethod
    def determine_band(cls, score_val: float) -> str:
        if score_val >= THRESHOLD_PASS:
            return PASS_BAND_PASS
        if score_val >= THRESHOLD_NEEDS_REVIEW:
            return PASS_BAND_NEEDS_REVIEW
        return PASS_BAND_FAIL

class Run(BaseModel):
    """Snapshot of an evaluation run execution."""
    id: str
    name: str
    status: str = STATUS_PENDING
    stop_reason: Optional[str] = STOP_REASON_COMPLETED
    experiment_spec: dict[str, Any]
    spec_hash: str
    total_cases: int = 0
    completed_cases: int = 0
    failed_cases: int = 0
    total_cost_usd: float = 0.0
    spending_cap_usd: Optional[float] = None
    seed: int = 42
    created_at: str
    completed_at: Optional[str] = None
    aggregate_metrics: dict[str, Any] = Field(default_factory=dict)

class GateConfig(BaseModel):
    """CI regression gating criteria."""
    min_aggregate_score: Optional[float] = Field(default=0.80)
    max_allowed_regressions: Optional[int] = Field(default=0)
    max_latency_p95_ms: Optional[float] = Field(default=None)
    max_cost_per_case_usd: Optional[float] = Field(default=None)
    required_pass_rate: Optional[float] = Field(default=None)

class GateEvaluation(BaseModel):
    """Result of evaluating a single gate rule."""
    rule_name: str
    threshold: Any
    actual_value: Any
    passed: bool
    message: str

class ComparisonResult(BaseModel):
    """Result of comparing baseline and candidate runs."""
    baseline_run_id: str
    candidate_run_id: str
    baseline_name: str
    candidate_name: str
    quality_delta: float
    latency_p50_delta_ms: float
    latency_p95_delta_ms: float
    cost_delta_usd: float
    baseline_metrics: dict[str, Any]
    candidate_metrics: dict[str, Any]
    regressions: list[dict[str, Any]]
    improvements: list[dict[str, Any]]
    gates_passed: bool = True
    gate_evaluations: list[GateEvaluation] = Field(default_factory=list)
