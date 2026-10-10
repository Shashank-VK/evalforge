import asyncio
import hashlib
import json
import os
import time
from typing import Optional
import httpx
from evalforge.adapters.base import ProviderAdapter
from evalforge.models import DatasetCase, ModelConfig, GenerationResult
from evalforge.constants import MODEL_PRICING
from evalforge.exceptions import ProviderError
from evalforge.storage.repository import Repository
from evalforge.logger import get_logger

logger = get_logger(__name__)

class OpenAIAdapter(ProviderAdapter):
    """Adapter for OpenAI and OpenAI-compatible hosted endpoints (e.g., LiteLLM, vLLM).
    Includes request hash caching, normalized token usage, pricing calculations,
    and provider error mapping.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, repository: Optional[Repository] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.repository = repository

    def _compute_request_hash(self, model: str, prompt: str, temperature: float, max_tokens: int) -> str:
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens
        }, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def generate(
        self,
        prompt: str,
        case: DatasetCase,
        config: ModelConfig,
        seed: int = 42
    ) -> GenerationResult:
        req_hash = self._compute_request_hash(config.model, prompt, config.temperature, config.max_tokens)

        # Check repository cache
        if self.repository:
            cached = self.repository.get_cached_response(req_hash)
            if cached:
                logger.info("Cache hit for request hash %s (case %s)", req_hash[:8], case.id)
                return GenerationResult(
                    response_text=cached["response_text"],
                    input_tokens=cached.get("input_tokens", 0),
                    output_tokens=cached.get("output_tokens", 0),
                    latency_ms=cached.get("latency_ms", 1.0),
                    estimated_cost_usd=cached.get("estimated_cost_usd", 0.0),
                    raw_payload={"cached": True, "request_hash": req_hash}
                )

        if not self.api_key:
            raise ProviderError(
                "OPENAI_API_KEY environment variable not configured",
                provider="openai",
                retryable=False,
                status_code=401
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "seed": seed
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

                if resp.status_code == 429 or resp.status_code >= 500:
                    raise ProviderError(
                        f"Provider HTTP error {resp.status_code}: {resp.text}",
                        provider="openai",
                        retryable=True,
                        status_code=resp.status_code
                    )
                if resp.status_code != 200:
                    raise ProviderError(
                        f"Provider HTTP {resp.status_code}: {resp.text}",
                        provider="openai",
                        retryable=False,
                        status_code=resp.status_code
                    )

                data = resp.json()
                choice = data["choices"][0]
                text = choice["message"]["content"]
                usage = data.get("usage", {})
                in_toks = usage.get("prompt_tokens", 0)
                out_toks = usage.get("completion_tokens", 0)

                pricing = MODEL_PRICING.get(config.model, {"input_per_1m": 0.50, "output_per_1m": 1.50})
                cost = (in_toks / 1_000_000.0) * pricing["input_per_1m"] + (out_toks / 1_000_000.0) * pricing["output_per_1m"]

                gen_res = GenerationResult(
                    response_text=text,
                    input_tokens=in_toks,
                    output_tokens=out_toks,
                    latency_ms=elapsed_ms,
                    estimated_cost_usd=cost,
                    raw_payload=data
                )

                # Cache in repository
                if self.repository:
                    await self.repository.set_cached_response(req_hash, {
                        "response_text": text,
                        "input_tokens": in_toks,
                        "output_tokens": out_toks,
                        "latency_ms": elapsed_ms,
                        "estimated_cost_usd": cost
                    })

                return gen_res

            except httpx.TimeoutException as e:
                raise ProviderError(f"Request timeout: {str(e)}", provider="openai", retryable=True)
            except httpx.RequestError as e:
                raise ProviderError(f"Connection error: {str(e)}", provider="openai", retryable=True)
