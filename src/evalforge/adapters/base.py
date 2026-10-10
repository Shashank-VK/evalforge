from abc import ABC, abstractmethod
from evalforge.models import DatasetCase, ModelConfig, GenerationResult

class ProviderAdapter(ABC):
    """Abstract base class for all model provider adapters."""
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        case: DatasetCase,
        config: ModelConfig,
        seed: int = 42
    ) -> GenerationResult:
        """Executes a generation call and returns normalized GenerationResult."""
        pass
