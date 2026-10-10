"""Typed errors the agent loop can turn into user-facing states."""


class LLMError(Exception):
    """Base class for every LLM client error."""


class ModelUnavailable(LLMError):
    """No model in the role's chain answered (E3 shows this as "model timeout")."""


class DeadlineExceeded(ModelUnavailable):
    """The solve's time budget ran out before a model answered."""


class LLMAuthError(LLMError):
    """401/403: the key is wrong or missing. Never retried, never falls back."""


class LLMRequestError(LLMError):
    """400/422: the request itself is bad. Never retried."""


class BudgetExceeded(LLMError):
    """Raised by a BudgetGuard to stop a call before it is sent."""


class JSONRepairFailed(LLMError):
    """The reply was not valid JSON for the schema, even after one repair."""

    def __init__(self, message: str, raw: str) -> None:
        super().__init__(message)
        self.raw = raw
