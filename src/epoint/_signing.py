from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from .errors import SignatureError


def encode_payload(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return base64.b64encode(body.encode()).decode()


def sign(private_key: str, data: str) -> str:
    digest = hashlib.sha1(f"{private_key}{data}{private_key}".encode()).digest()
    return base64.b64encode(digest).decode()


def matches(private_key: str, data: str, signature: str) -> bool:
    return hmac.compare_digest(sign(private_key, data), signature)


def decode_data(data: str) -> dict[str, Any]:
    try:
        decoded = base64.b64decode(data)
        parsed = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        raise SignatureError("data is not valid base64 encoded JSON") from exc
    if not isinstance(parsed, dict):
        raise SignatureError("data did not decode to an object")
    return parsed
