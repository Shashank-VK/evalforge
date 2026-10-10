"""Custom exceptions for EvalForge."""

class EvalForgeError(Exception):
    """Base exception for all EvalForge errors."""
    pass

class ValidationFailedError(EvalForgeError):
    """Raised when dataset, configuration, or experiment specification validation fails."""
    pass

class SpendingCapExceededError(EvalForgeError):
    """Raised when preflight cost estimate or runtime spending exceeds the spending cap."""
    pass

class ProviderError(EvalForgeError):
    """Raised when an adapter encounters an unrecoverable provider failure."""
    def __init__(self, message: str, provider: str, retryable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code

class GateFailureError(EvalForgeError):
    """Raised when a CI regression gate condition is not met."""
    pass

class UnauthorizedError(EvalForgeError):
    """Raised when an unauthorized demo action is attempted."""
    pass
