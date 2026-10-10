from typing import Optional
from evalforge.adapters.base import ProviderAdapter
from evalforge.adapters.fixture import FixtureAdapter
from evalforge.adapters.mock import MockAdapter
from evalforge.adapters.openai_adapter import OpenAIAdapter
from evalforge.storage.repository import Repository
from evalforge.config import get_settings

def get_adapter(
    provider: str,
    repository: Optional[Repository] = None,
    fixtures_path: Optional[str] = None
) -> ProviderAdapter:
    """Factory to instantiate the appropriate provider adapter."""
    settings = get_settings()
    provider_lower = provider.lower()
    
    if provider_lower in ("fixture", "recorded", "offline"):
        path = fixtures_path or settings.fixtures_path
        return FixtureAdapter(fixtures_path=path)
    elif provider_lower in ("mock", "deterministic"):
        return MockAdapter()
    elif provider_lower in ("openai", "litellm", "hosted"):
        return OpenAIAdapter(repository=repository)
    else:
        # Fallback to MockAdapter with warning
        return MockAdapter()
