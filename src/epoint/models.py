from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class Response:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    @property
    def status(self) -> str | None:
        value = self.raw.get("status")
        return str(value) if value is not None else None

    @property
    def ok(self) -> bool:
        return self.raw.get("status") == "success"

    @property
    def transaction(self) -> str | None:
        value = self.raw.get("transaction")
        return str(value) if value is not None else None

    @property
    def redirect_url(self) -> str | None:
        value = self.raw.get("redirect_url")
        return str(value) if value is not None else None

    @property
    def message(self) -> str | None:
        value = self.raw.get("message")
        return str(value) if value is not None else None

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def __contains__(self, key: str) -> bool:
        return key in self.raw

    def __repr__(self) -> str:
        return f"Response({self.raw!r})"


@dataclass(frozen=True)
class Callback:
    order_id: str
    status: str
    code: str
    message: str
    transaction: str
    bank_transaction: str
    operation_code: str
    rrn: str | None
    card_mask: str | None
    card_name: str | None
    amount: float
    other_attr: Any
    raw: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.status == "success"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Callback:
        return cls(
            order_id=str(data.get("order_id", "")),
            status=str(data.get("status", "")),
            code=str(data.get("code", "")),
            message=str(data.get("message", "")),
            transaction=str(data.get("transaction", "")),
            bank_transaction=str(data.get("bank_transaction", "")),
            operation_code=str(data.get("operation_code", "")),
            rrn=data.get("rrn"),
            card_mask=data.get("card_mask"),
            card_name=data.get("card_name"),
            amount=float(data["amount"]) if data.get("amount") is not None else 0.0,
            other_attr=data.get("other_attr"),
            raw=data,
        )
