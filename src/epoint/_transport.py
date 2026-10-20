from __future__ import annotations

from typing import Any

from . import _signing
from .enums import Status
from .errors import GatewayError, TransportError
from .models import Response


def build_form(public_key: str, private_key: str, payload: dict[str, Any]) -> dict[str, str]:
    body = {"public_key": public_key, **{k: v for k, v in payload.items() if v is not None}}
    data = _signing.encode_payload(body)
    return {"data": data, "signature": _signing.sign(private_key, data)}


def build_json(public_key: str, private_key: str, payload: dict[str, Any]) -> dict[str, str]:
    return build_form(public_key, private_key, payload)


def is_payment_state(status_code: int, body: dict[str, Any]) -> bool:
    return 200 <= status_code < 300 and body.get("status") == Status.ERROR and "transaction" in body


def parse(status_code: int, body: Any, *, payment_status: bool = False) -> Response:
    if not isinstance(body, dict):
        raise TransportError(f"unexpected response body: {body!r}", status_code=status_code)

    if payment_status and is_payment_state(status_code, body):
        return Response(body)

    if body.get("status") == Status.ERROR:
        raise GatewayError(
            str(body.get("message") or "request refused"),
            code=str(body["code"]) if body.get("code") is not None else None,
            status=str(body.get("status")),
            payload=body,
        )

    if status_code >= 400:
        detail = body.get("detail") or body.get("message") or f"HTTP {status_code}"
        raise TransportError(str(detail), status_code=status_code)

    return Response(body)
