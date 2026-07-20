from __future__ import annotations

from . import _signing
from .errors import SignatureError
from .models import Callback


def verify_callback(private_key: str, data: str, signature: str) -> Callback:
    if not _signing.matches(private_key, data, signature):
        raise SignatureError("callback signature does not match")
    return Callback.from_dict(_signing.decode_data(data))
