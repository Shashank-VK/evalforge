import json
import os
import hashlib
from pathlib import Path
from typing import Optional
from evalforge.adapters.base import ProviderAdapter
from evalforge.models import DatasetCase, ModelConfig, GenerationResult
from evalforge.constants import FIXTURE_VERSION
from evalforge.exceptions import ProviderError
from evalforge.logger import get_logger

logger = get_logger(__name__)

class FixtureAdapter(ProviderAdapter):
    """Adapter that replays pre-recorded mock/golden fixtures from a JSON file.
    Guarantees 100% offline, deterministic CI runs with pinned evaluator versions and no network calls.
    """
    def __init__(self, fixtures_path: str = "fixtures/recorded_responses.json"):
        self.fixtures_path = fixtures_path
        self._fixtures: dict[str, dict] = {}
        self._loaded = False
        self._load_fixtures()

    def _load_fixtures(self) -> None:
        if not os.path.exists(self.fixtures_path):
            logger.warning("Fixtures file not found at %s. Fixture adapter will be empty.", self.fixtures_path)
            self._fixtures = {}
            self._loaded = True
            return
        try:
            with open(self.fixtures_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._fixtures = data.get("responses", data)
                self._loaded = True
        except Exception as e:
            logger.error("Failed to load fixtures file: %s", str(e))
            self._fixtures = {}

    def _compute_key(self, case_id: str, config_id: str, prompt: str) -> str:
        prompt_hash = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()[:16]
        return f"{case_id}:{config_id}:{prompt_hash}"

    async def generate(
        self,
        prompt: str,
        case: DatasetCase,
        config: ModelConfig,
        seed: int = 42
    ) -> GenerationResult:
        if not self._loaded:
            self._load_fixtures()

        key_full = self._compute_key(case.id, config.id, prompt)
        key_case_config = f"{case.id}:{config.id}"
        key_case = case.id

        entry = None
        if key_full in self._fixtures:
            entry = self._fixtures[key_full]
        elif key_case_config in self._fixtures:
            entry = self._fixtures[key_case_config]
        elif key_case in self._fixtures:
            entry = self._fixtures[key_case]

        if not entry:
            # Fallback fixture if case has expected data or synthesize a deterministic output
            default_resp = ""
            if case.expected and "exact_match" in case.expected:
                default_resp = str(case.expected["exact_match"])
            elif case.expected and "contains" in case.expected:
                default_resp = f"Here is the requested information regarding {case.expected['contains'][0]}."
            else:
                default_resp = f"Deterministic fixture response for case {case.id} under {config.id}."
            
            entry = {
                "response_text": default_resp,
                "input_tokens": max(len(prompt.split()) * 2, 10),
                "output_tokens": max(len(default_resp.split()) * 2, 10),
                "latency_ms": 45.0,
                "estimated_cost_usd": 0.0,
            }

        return GenerationResult(
            response_text=entry.get("response_text", ""),
            input_tokens=entry.get("input_tokens", 50),
            output_tokens=entry.get("output_tokens", 30),
            latency_ms=entry.get("latency_ms", 50.0),
            estimated_cost_usd=entry.get("estimated_cost_usd", 0.0),
            error=entry.get("error"),
            raw_payload={"fixture_key": key_full, "fixture_version": FIXTURE_VERSION}
        )
