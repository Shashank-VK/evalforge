import asyncio
import hashlib
import json
from typing import Optional
from evalforge.adapters.base import ProviderAdapter
from evalforge.models import DatasetCase, ModelConfig, GenerationResult
from evalforge.exceptions import ProviderError

class MockAdapter(ProviderAdapter):
    """Deterministic mock provider adapter for local development and testing.
    Can simulate delays, transient errors, and generates predictable outputs.
    """
    def __init__(self, failure_count_by_case: Optional[dict[str, int]] = None, latency_ms: float = 20.0):
        # case_id -> number of times it should fail before succeeding
        self.failure_count_by_case: dict[str, int] = failure_count_by_case or {}
        self.attempt_counter: dict[str, int] = {}
        self.latency_ms = latency_ms

    async def generate(
        self,
        prompt: str,
        case: DatasetCase,
        config: ModelConfig,
        seed: int = 42
    ) -> GenerationResult:
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

        # Check simulated transient failures
        attempts = self.attempt_counter.get(case.id, 0)
        self.attempt_counter[case.id] = attempts + 1
        needed_failures = self.failure_count_by_case.get(case.id, 0)
        if attempts < needed_failures:
            raise ProviderError(
                f"Simulated transient 503 error for {case.id} (attempt {attempts + 1})",
                provider="mock",
                retryable=True,
                status_code=503
            )

        # Generate deterministic response
        resp_text = ""
        if case.expected:
            if "exact_match" in case.expected:
                resp_text = str(case.expected["exact_match"])
            elif "contains" in case.expected and case.expected["contains"]:
                keywords = case.expected["contains"]
                resp_text = f"The approved policy state is: {', '.join(keywords)}. Please refer to [doc1#chunk1] for details."
            elif "json_schema" in case.expected:
                resp_text = json.dumps({"status": "success", "result": case.input.get("question", "processed")})
            else:
                resp_text = f"Mock response for question: {case.input.get('question', 'default')} with config {config.id}."
        else:
            resp_text = f"Mock response for {case.id} using prompt: {prompt[:30]}..."

        input_tokens = len(prompt.split()) + 15
        output_tokens = len(resp_text.split()) + 10
        
        return GenerationResult(
            response_text=resp_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=self.latency_ms,
            estimated_cost_usd=0.0,
            raw_payload={"mock_seed": seed, "config_id": config.id}
        )
