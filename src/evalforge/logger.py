import logging
import json
import re
from typing import Any
from evalforge.config import get_settings

REDACT_KEYS = {"api_key", "token", "secret", "password", "authorization"}
SENSITIVE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
]

def sanitize_value(key: str, value: Any) -> Any:
    if isinstance(key, str) and any(k in key.lower() for k in REDACT_KEYS):
        return "[REDACTED]"
    if isinstance(value, str):
        for pattern in SENSITIVE_PATTERNS:
            value = pattern.sub("[REDACTED]", value)
        return value
    if isinstance(value, dict):
        return {k: sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(key, item) for item in value]
    return value

class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        settings = get_settings()
        data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "run_id"):
            data["run_id"] = record.run_id
        if hasattr(record, "case_id"):
            data["case_id"] = record.case_id
        if hasattr(record, "provider"):
            data["provider"] = record.provider
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            data.update(record.extra_fields)

        if settings.redact_sensitive:
            data = sanitize_value("root", data)
        return json.dumps(data)

def get_logger(name: str = "evalforge") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
