from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .enums import OK_STATUSES, SETTLED_STATUSES, B2BWebhookStatus


def _text(value: Any) -> str | None:
    return str(value) if value is not None else None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = Decimal(value.strip())
        except InvalidOperation:
            return None
        return float(parsed) if parsed.is_finite() else None
    return None


class Response:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    @property
    def status(self) -> str | None:
        value = self.raw.get("status")
        return str(value) if value is not None else None

    @property
    def ok(self) -> bool:
        return self.raw.get("status") in OK_STATUSES

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

    @property
    def trace_id(self) -> str | None:
        return _text(self.raw.get("trace_id"))

    @property
    def code(self) -> str | None:
        return _text(self.raw.get("code"))

    @property
    def bank_transaction(self) -> str | None:
        return _text(self.raw.get("bank_transaction"))

    @property
    def bank_response(self) -> str | None:
        return _text(self.raw.get("bank_response"))

    @property
    def operation_code(self) -> str | None:
        return _text(self.raw.get("operation_code"))

    @property
    def rrn(self) -> str | None:
        return _text(self.raw.get("rrn"))

    @property
    def card_name(self) -> str | None:
        return _text(self.raw.get("card_name"))

    @property
    def card_mask(self) -> str | None:
        return _text(self.raw.get("card_mask"))

    @property
    def card_id(self) -> str | None:
        return _text(self.raw.get("card_id"))

    @property
    def order_id(self) -> str | None:
        return _text(self.raw.get("order_id"))

    @property
    def widget_url(self) -> str | None:
        return _text(self.raw.get("widget_url"))

    @property
    def amount(self) -> float | None:
        return _number(self.raw.get("amount"))

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
    bank_response: str | None = None
    trace_id: str | None = None
    card_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in SETTLED_STATUSES

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
            bank_response=_text(data.get("bank_response")),
            trace_id=_text(data.get("trace_id")),
            card_id=_text(data.get("card_id")),
        )


@dataclass(frozen=True)
class CheckoutForm:
    url: str
    data: str
    signature: str

    @property
    def fields(self) -> dict[str, str]:
        return {"data": self.data, "signature": self.signature}


@dataclass(frozen=True)
class B2BWebhook:
    order_id: str
    status: str
    amount: float | None
    payee_iban: str | None
    payee_name: str | None
    error_message: str | None
    raw: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.status == B2BWebhookStatus.SUCCESS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> B2BWebhook:
        return cls(
            order_id=str(data.get("order_id", "")),
            status=str(data.get("status", "")),
            amount=_number(data.get("amount")),
            payee_iban=_text(data.get("payee_iban")),
            payee_name=_text(data.get("payee_name")),
            error_message=_text(data.get("error_message")),
            raw=data,
        )
