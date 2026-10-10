import os
from pydantic import BaseModel, Field

class Settings(BaseModel):
    """Application settings loaded from environment variables."""
    demo_mode: bool = Field(default_factory=lambda: os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes"))
    demo_admin_key: str = Field(default_factory=lambda: os.getenv("DEMO_ADMIN_KEY", "evalforge-demo-secret-key-2026"))
    db_path: str = Field(default_factory=lambda: os.getenv("EVALFORGE_DB_PATH", "evalforge.db"))
    fixtures_path: str = Field(default_factory=lambda: os.getenv("EVALFORGE_FIXTURES_PATH", "fixtures/recorded_responses.json"))
    max_run_cost_usd: float = Field(default_factory=lambda: float(os.getenv("MAX_RUN_COST_USD", "10.0")))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    redact_sensitive: bool = Field(default_factory=lambda: os.getenv("REDACT_SENSITIVE", "true").lower() in ("true", "1", "yes"))

_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

def set_settings(new_settings: Settings) -> None:
    global _settings
    _settings = new_settings
