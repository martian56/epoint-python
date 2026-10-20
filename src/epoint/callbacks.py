from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from . import _signing
from .errors import EpointError, SignatureError
from .models import B2BWebhook, Callback


def verify_callback(private_key: str, data: str, signature: str) -> Callback:
    if not _signing.matches(private_key, data, signature):
        raise SignatureError("callback signature does not match")
    return Callback.from_dict(_signing.decode_data(data))


def parse_b2b_webhook(body: str | bytes | Mapping[str, Any]) -> B2BWebhook:
    if isinstance(body, Mapping):
        data: Any = dict(body)
    else:
        try:
            data = json.loads(body)
        except ValueError as exc:
            raise EpointError("b2b webhook body is not valid JSON") from exc
    if not isinstance(data, dict):
        raise EpointError("b2b webhook body is not a JSON object")
    return B2BWebhook.from_dict(data)
