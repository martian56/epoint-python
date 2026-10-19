from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, NamedTuple

Amount = int | float | str | Decimal


def money(value: Amount) -> str:
    return f"{Decimal(str(value)):.2f}"


@dataclass(frozen=True)
class Defaults:
    language: str
    currency: str
    success_redirect_url: str | None
    error_redirect_url: str | None


class Call(NamedTuple):
    path: str
    payload: dict[str, Any]


def _checkout(
    d: Defaults,
    path: str,
    amount: Amount,
    order_id: str,
    description: str | None,
    language: str | None,
    currency: str | None,
    success_redirect_url: str | None,
    error_redirect_url: str | None,
    other_attr: Any,
    extra: dict[str, Any] | None = None,
) -> Call:
    payload: dict[str, Any] = {
        "amount": money(amount),
        "currency": currency or d.currency,
        "language": language or d.language,
        "order_id": order_id,
        "description": description,
        "other_attr": other_attr,
        "success_redirect_url": success_redirect_url or d.success_redirect_url,
        "error_redirect_url": error_redirect_url or d.error_redirect_url,
    }
    if extra:
        payload.update(extra)
    return Call(path, payload)


def create_payment(
    d: Defaults,
    amount: Amount,
    order_id: str,
    description: str | None,
    language: str | None,
    currency: str | None,
    success_redirect_url: str | None,
    error_redirect_url: str | None,
    other_attr: Any,
) -> Call:
    return _checkout(
        d,
        "/api/1/request",
        amount,
        order_id,
        description,
        language,
        currency,
        success_redirect_url,
        error_redirect_url,
        other_attr,
    )


def create_payment_request(
    d: Defaults,
    amount: Amount,
    order_id: str,
    description: str | None,
    language: str | None,
    currency: str | None,
    success_redirect_url: str | None,
    error_redirect_url: str | None,
    other_attr: Any,
) -> Call:
    return _checkout(
        d,
        "/api/1/payment-request",
        amount,
        order_id,
        description,
        language,
        currency,
        success_redirect_url,
        error_redirect_url,
        other_attr,
    )


def create_amex_payment(
    d: Defaults,
    amount: Amount,
    order_id: str,
    description: str | None,
    language: str | None,
    currency: str | None,
    success_redirect_url: str | None,
    error_redirect_url: str | None,
    other_attr: Any,
) -> Call:
    return _checkout(
        d,
        "/api/1/amex-request",
        amount,
        order_id,
        description,
        language,
        currency,
        success_redirect_url,
        error_redirect_url,
        other_attr,
    )


def change_payment_sum(
    d: Defaults,
    amount: Amount,
    order_id: str,
    description: str | None,
    language: str | None,
    currency: str | None,
    success_redirect_url: str | None,
    error_redirect_url: str | None,
    other_attr: Any,
) -> Call:
    return _checkout(
        d,
        "/api/1/payment-change-sum",
        amount,
        order_id,
        description,
        language,
        currency,
        success_redirect_url,
        error_redirect_url,
        other_attr,
    )


def reserve(
    d: Defaults,
    amount: Amount,
    order_id: str,
    description: str | None,
    language: str | None,
    currency: str | None,
    success_redirect_url: str | None,
    error_redirect_url: str | None,
    other_attr: Any,
) -> Call:
    return _checkout(
        d,
        "/api/1/pre-auth-request",
        amount,
        order_id,
        description,
        language,
        currency,
        success_redirect_url,
        error_redirect_url,
        other_attr,
    )


def create_split_payment(
    d: Defaults,
    amount: Amount,
    order_id: str,
    split_account: str,
    split_amount: Amount,
    description: str | None,
    language: str | None,
    currency: str | None,
    success_redirect_url: str | None,
    error_redirect_url: str | None,
    other_attr: Any,
) -> Call:
    return _checkout(
        d,
        "/api/1/split-request",
        amount,
        order_id,
        description,
        language,
        currency,
        success_redirect_url,
        error_redirect_url,
        other_attr,
        extra={"split_user": split_account, "split_amount": money(split_amount)},
    )


def pay_by_installment(
    d: Defaults,
    amount: Amount,
    order_id: str,
    installment_card_id: str,
    installment_month: int,
    description: str | None,
    language: str | None,
    currency: str | None,
    success_redirect_url: str | None,
    error_redirect_url: str | None,
) -> Call:
    return _checkout(
        d,
        "/api/1/installment-request",
        amount,
        order_id,
        description,
        language,
        currency,
        success_redirect_url,
        error_redirect_url,
        None,
        extra={
            "installment_card_id": installment_card_id,
            "installment_month": installment_month,
        },
    )


def get_status(transaction: str) -> Call:
    return Call("/api/1/get-status", {"transaction": transaction})


def get_card_status(card_id: str) -> Call:
    return Call("/api/1/get-status-card", {"card_id": card_id})


def capture(transaction: str, amount: Amount) -> Call:
    return Call(
        "/api/1/pre-auth-complete",
        {"transaction": transaction, "amount": money(amount)},
    )


def split_charge_saved_card(
    d: Defaults,
    card_id: str,
    amount: Amount,
    order_id: str,
    split_account: str,
    split_amount: Amount,
    description: str | None,
    language: str | None,
    currency: str | None,
) -> Call:
    return Call(
        "/api/1/split-execute-pay",
        {
            "card_id": card_id,
            "amount": money(amount),
            "currency": currency or d.currency,
            "language": language or d.language,
            "order_id": order_id,
            "split_user": split_account,
            "split_amount": money(split_amount),
            "description": description,
        },
    )


def register_card(
    d: Defaults,
    description: str | None,
    language: str | None,
    for_payouts: bool,
    success_redirect_url: str | None = None,
    error_redirect_url: str | None = None,
) -> Call:
    return Call(
        "/api/1/card-registration",
        {
            "language": language or d.language,
            "refund": 1 if for_payouts else 0,
            "description": description,
            "success_redirect_url": success_redirect_url or d.success_redirect_url,
            "error_redirect_url": error_redirect_url or d.error_redirect_url,
        },
    )


def register_card_and_pay(
    d: Defaults,
    amount: Amount,
    order_id: str,
    description: str | None,
    language: str | None,
    currency: str | None,
    success_redirect_url: str | None,
    error_redirect_url: str | None,
) -> Call:
    return _checkout(
        d,
        "/api/1/card-registration-with-pay",
        amount,
        order_id,
        description,
        language,
        currency,
        success_redirect_url,
        error_redirect_url,
        None,
    )


def charge_saved_card(
    d: Defaults,
    card_id: str,
    amount: Amount,
    order_id: str,
    description: str | None,
    language: str | None,
    currency: str | None,
) -> Call:
    return Call(
        "/api/1/execute-pay",
        {
            "card_id": card_id,
            "amount": money(amount),
            "currency": currency or d.currency,
            "language": language or d.language,
            "order_id": order_id,
            "description": description,
        },
    )


def refund(
    d: Defaults,
    card_id: str,
    amount: Amount,
    order_id: str,
    description: str | None,
    language: str | None,
    currency: str | None,
) -> Call:
    return Call(
        "/api/1/refund-request",
        {
            "card_id": card_id,
            "amount": money(amount),
            "currency": currency or d.currency,
            "language": language or d.language,
            "order_id": order_id,
            "description": description,
        },
    )


def reverse(
    d: Defaults,
    transaction: str,
    amount: Amount | None,
    language: str | None,
    currency: str | None,
) -> Call:
    return Call(
        "/api/1/reverse",
        {
            "transaction": transaction,
            "amount": money(amount) if amount is not None else None,
            "currency": currency or d.currency,
            "language": language or d.language,
        },
    )


def get_installment_plans(
    d: Defaults, order_id: str, amount: Amount | None, language: str | None, currency: str | None
) -> Call:
    return Call(
        "/api/1/get-installment-request",
        {
            "order_id": order_id,
            "amount": money(amount) if amount is not None else None,
            "currency": currency or d.currency,
            "language": language or d.language,
        },
    )


def pay_with_wallet(
    d: Defaults,
    wallet_id: str,
    amount: Amount,
    order_id: str,
    description: str | None,
    language: str | None,
    currency: str | None,
) -> Call:
    return Call(
        "/api/1/wallet/payment",
        {
            "wallet_id": wallet_id,
            "amount": money(amount),
            "currency": currency or d.currency,
            "language": language or d.language,
            "order_id": order_id,
            "description": description,
        },
    )


def create_widget(amount: Amount, order_id: str, description: str) -> Call:
    return Call(
        "/api/1/token/widget",
        {"amount": money(amount), "order_id": order_id, "description": description},
    )


def _invoice(
    amount: Amount,
    period_from: str,
    period_to: str,
    name: str | None,
    description: str | None,
    phone: str | None,
    email: str | None,
    display: bool,
    save_as_template: bool,
    allow_installment: bool,
    extra: dict[str, Any],
) -> dict[str, Any]:
    return {
        "sum": money(amount),
        "period_from": period_from,
        "period_to": period_to,
        "name": name,
        "description": description,
        "phone": phone,
        "email": email,
        "display": 1 if display else 0,
        "save_as_template": 1 if save_as_template else 0,
        "status_installment": 1 if allow_installment else 0,
        **extra,
    }


def create_invoice(
    amount: Amount,
    period_from: str,
    period_to: str,
    name: str | None,
    description: str | None,
    phone: str | None,
    email: str | None,
    tin: str | None,
    contract_number: str | None,
    merchant_order_id: str | None,
    display: bool,
    save_as_template: bool,
    allow_installment: bool,
) -> Call:
    payload = _invoice(
        amount,
        period_from,
        period_to,
        name,
        description,
        phone,
        email,
        display,
        save_as_template,
        allow_installment,
        {
            "inn": tin,
            "contract_number": contract_number,
            "merchant_order_id": merchant_order_id,
        },
    )
    return Call("/api/1/invoices/create", payload)


def update_invoice(
    invoice_id: int,
    amount: Amount,
    period_from: str,
    period_to: str,
    name: str | None,
    description: str | None,
    phone: str | None,
    email: str | None,
    display: bool,
    save_as_template: bool,
    allow_installment: bool,
) -> Call:
    payload = _invoice(
        amount,
        period_from,
        period_to,
        name,
        description,
        phone,
        email,
        display,
        save_as_template,
        allow_installment,
        {"id": invoice_id},
    )
    return Call("/api/1/invoices/update", payload)


def get_invoice(invoice_id: int) -> Call:
    return Call("/api/1/invoices/view", {"id": invoice_id})


def list_invoices(kind: str | None, order: str | None) -> Call:
    return Call("/api/1/invoices/list", {"type": kind, "order": order})


def send_invoice_sms(invoice_id: int, phone: str) -> Call:
    return Call("/api/1/invoices/send-sms", {"id": invoice_id, "phone": phone})


def send_invoice_email(invoice_id: int, email: str) -> Call:
    return Call("/api/1/invoices/send-email", {"id": invoice_id, "email": email})


def create_bank_transfer(
    order_id: str,
    amount: Amount,
    description: str,
    iban: str,
    name: str,
    tin: str,
    bank_code: str,
    bank_name: str | None,
    email: str | None,
    address: str | None,
    additional_info: str | None,
    webhook_url: str | None,
) -> Call:
    return Call(
        "/api/1/b2b/payment",
        {
            "order_id": order_id,
            "amount": money(amount),
            "description": description,
            "iban": iban,
            "name": name,
            "tin": tin,
            "bank_code": bank_code,
            "bank_name": bank_name,
            "email": email,
            "address": address,
            "additional_info": additional_info,
            "webhook_url": webhook_url,
        },
    )
