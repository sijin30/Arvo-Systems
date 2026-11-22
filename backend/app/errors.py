from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """A business-rule failure that maps to a clean HTTP error."""

    def __init__(self, status_code: int, code: str, message: str, **extra: Any):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra

    def body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, **self.extra}}


def not_found(what: str = "Ticket") -> DomainError:
    return DomainError(404, "not_found", f"{what} not found")


def forbidden(message: str, code: str = "forbidden") -> DomainError:
    return DomainError(403, code, message)


def conflict(code: str, message: str, **extra: Any) -> DomainError:
    return DomainError(409, code, message, **extra)


def bad_request(code: str, message: str) -> DomainError:
    return DomainError(400, code, message)
