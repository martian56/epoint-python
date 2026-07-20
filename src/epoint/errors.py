from __future__ import annotations

from typing import Any


class EpointError(Exception):
    pass


class SignatureError(EpointError):
    pass


class TransportError(EpointError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GatewayError(EpointError):
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.payload = payload or {}
