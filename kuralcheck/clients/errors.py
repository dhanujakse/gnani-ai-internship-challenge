"""Typed errors for Gnani API calls. Messages carry status codes only, never keys or content."""


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ApiBadRequest(ApiError):
    """400: bad input. Never retried."""


class ApiAuthError(ApiError):
    """403: bad API key or no credits left. Never retried."""


class ApiRateLimited(ApiError):
    """429: retried once."""


class ApiServerError(ApiError):
    """5xx or network timeout: retried once."""
