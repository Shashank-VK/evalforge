from typing import Callable, Optional
from evalforge.models import DatasetCase, ModelConfig
from evalforge.constants import MODEL_PRICING

class CostTracker:
    """Tracks token spending and performs preflight cost calculations."""
    
    @staticmethod
    def estimate_preflight_cost(
        cases: list[DatasetCase],
        configs: list[ModelConfig],
        prompt_renderer: Callable[[ModelConfig, DatasetCase], str]
    ) -> float:
        """Calculates preflight estimated cost for all case-config combinations."""
        total_estimate = 0.0
        for config in configs:
            pricing = MODEL_PRICING.get(config.model, {"input_per_1m": 0.50, "output_per_1m": 1.50})
            input_price_per_token = pricing["input_per_1m"] / 1_000_000.0
            output_price_per_token = pricing["output_per_1m"] / 1_000_000.0

            for case in cases:
                prompt = prompt_renderer(config, case)
                # Approximate 1 token = 0.75 words, or word count * 1.3
                est_in_tokens = max(int(len(prompt.split()) * 1.3), 10)
                est_out_tokens = min(config.max_tokens, 250)
                
                cost = (est_in_tokens * input_price_per_token) + (est_out_tokens * output_price_per_token)
                total_estimate += cost
        return round(total_estimate, 6)

    def __init__(self, spending_cap_usd: Optional[float] = None):
        self.spending_cap_usd = spending_cap_usd
        self.accumulated_cost_usd = 0.0

    def add_cost(self, cost: float) -> None:
        self.accumulated_cost_usd += cost

    def is_cap_exceeded(self) -> bool:
        if self.spending_cap_usd is None:
            return False
        return self.accumulated_cost_usd >= self.spending_cap_usd
