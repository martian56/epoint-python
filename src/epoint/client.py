from __future__ import annotations

import os
from decimal import Decimal
from types import TracebackType
from typing import Any

import httpx

from . import _transport
from .callbacks import verify_callback
from .errors import TransportError
from .models import Callback, Response

Amount = int | float | str | Decimal

PRODUCTION_URL = "https://epoint.az"


def _money(value: Amount) -> str:
    return f"{Decimal(str(value)):.2f}"


class EpointClient:
    def __init__(
        self,
        public_key: str,
        private_key: str,
        *,
        base_url: str = PRODUCTION_URL,
        language: str = "az",
        currency: str = "AZN",
        success_redirect_url: str | None = None,
        error_redirect_url: str | None = None,
        timeout: float = 30.0,
        transport: httpx.Client | None = None,
    ) -> None:
        self.public_key = public_key
        self.private_key = private_key
        self.base_url = base_url.rstrip("/")
        self.language = language
        self.currency = currency
        self.success_redirect_url = success_redirect_url
        self.error_redirect_url = error_redirect_url
        self._http = transport or httpx.Client(timeout=timeout)

    @classmethod
    def from_env(cls, **overrides: Any) -> EpointClient:
        public_key = os.environ["EPOINT_PUBLIC_KEY"]
        private_key = os.environ["EPOINT_PRIVATE_KEY"]
        params: dict[str, Any] = {
            "base_url": os.environ.get("EPOINT_BASE_URL", PRODUCTION_URL),
            "language": os.environ.get("EPOINT_LANGUAGE", "az"),
            "success_redirect_url": os.environ.get("EPOINT_SUCCESS_REDIRECT_URL"),
            "error_redirect_url": os.environ.get("EPOINT_FAILED_REDIRECT_URL"),
        }
        params.update(overrides)
        return cls(public_key, private_key, **params)

    def _redirects(self, success: str | None, error: str | None) -> dict[str, str | None]:
        return {
            "success_redirect_url": success or self.success_redirect_url,
            "error_redirect_url": error or self.error_redirect_url,
        }

    def _send(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._http.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise TransportError(
                f"response was not JSON: {response.text[:200]}",
                status_code=response.status_code,
            ) from exc
        return response.status_code, body

    def _post(self, path: str, payload: dict[str, Any]) -> Response:
        form = _transport.build_form(self.public_key, self.private_key, payload)
        status, body = self._send("POST", path, data=form)
        return _transport.parse(status, body)

    def _post_raw(self, path: str, payload: dict[str, Any]) -> Any:
        form = _transport.build_form(self.public_key, self.private_key, payload)
        status, body = self._send("POST", path, data=form)
        if isinstance(body, dict):
            _transport.parse(status, body)
        return body

    def _post_json(self, path: str, payload: dict[str, Any]) -> Response:
        form = _transport.build_json(self.public_key, self.private_key, payload)
        status, body = self._send("POST", path, json=form)
        return _transport.parse(status, body)

    def create_payment(
        self,
        amount: Amount,
        order_id: str,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
        success_redirect_url: str | None = None,
        error_redirect_url: str | None = None,
        other_attr: Any = None,
    ) -> Response:
        """Start a payment and return the redirect URL the customer should be sent to."""
        return self._post(
            "/api/1/request",
            {
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "description": description,
                "other_attr": other_attr,
                **self._redirects(success_redirect_url, error_redirect_url),
            },
        )

    def create_payment_request(
        self,
        amount: Amount,
        order_id: str,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
        success_redirect_url: str | None = None,
        error_redirect_url: str | None = None,
        other_attr: Any = None,
    ) -> Response:
        """Same as create_payment, for the payment types epoint documents separately."""
        return self._post(
            "/api/1/payment-request",
            {
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "description": description,
                "other_attr": other_attr,
                **self._redirects(success_redirect_url, error_redirect_url),
            },
        )

    def create_amex_payment(
        self,
        amount: Amount,
        order_id: str,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
        success_redirect_url: str | None = None,
        error_redirect_url: str | None = None,
        other_attr: Any = None,
    ) -> Response:
        """Start an American Express payment. Needs AMEX enabled on the account."""
        return self._post(
            "/api/1/amex-request",
            {
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "description": description,
                "other_attr": other_attr,
                **self._redirects(success_redirect_url, error_redirect_url),
            },
        )

    def change_payment_sum(
        self,
        amount: Amount,
        order_id: str,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
        success_redirect_url: str | None = None,
        error_redirect_url: str | None = None,
        other_attr: Any = None,
    ) -> Response:
        """Re-price an order before the customer pays."""
        return self._post(
            "/api/1/payment-change-sum",
            {
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "description": description,
                "other_attr": other_attr,
                **self._redirects(success_redirect_url, error_redirect_url),
            },
        )

    def get_status(self, transaction: str) -> Response:
        """Look up a transaction by its epoint id."""
        return self._post("/api/1/get-status", {"transaction": transaction})

    def create_split_payment(
        self,
        amount: Amount,
        order_id: str,
        split_account: str,
        split_amount: Amount,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
        success_redirect_url: str | None = None,
        error_redirect_url: str | None = None,
        other_attr: Any = None,
    ) -> Response:
        """Start a payment split with another epoint account."""
        return self._post(
            "/api/1/split-request",
            {
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "split_user": split_account,
                "split_amount": _money(split_amount),
                "description": description,
                "other_attr": other_attr,
                **self._redirects(success_redirect_url, error_redirect_url),
            },
        )

    def split_charge_saved_card(
        self,
        card_id: str,
        amount: Amount,
        order_id: str,
        split_account: str,
        split_amount: Amount,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
    ) -> Response:
        """Charge a saved card and split the amount with another account."""
        return self._post(
            "/api/1/split-execute-pay",
            {
                "card_id": card_id,
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "split_user": split_account,
                "split_amount": _money(split_amount),
                "description": description,
            },
        )

    def reserve(
        self,
        amount: Amount,
        order_id: str,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
        success_redirect_url: str | None = None,
        error_redirect_url: str | None = None,
        other_attr: Any = None,
    ) -> Response:
        """Reserve funds without capturing them. Complete later with capture."""
        return self._post(
            "/api/1/pre-auth-request",
            {
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "description": description,
                "other_attr": other_attr,
                **self._redirects(success_redirect_url, error_redirect_url),
            },
        )

    def capture(self, transaction: str, amount: Amount) -> Response:
        """Capture a previously reserved amount, in full or in part."""
        return self._post(
            "/api/1/pre-auth-complete",
            {"transaction": transaction, "amount": _money(amount)},
        )

    def register_card(
        self,
        *,
        description: str | None = None,
        language: str | None = None,
        for_payouts: bool = False,
    ) -> Response:
        """Start card registration. The customer confirms it on the checkout page."""
        return self._post(
            "/api/1/card-registration",
            {
                "language": language or self.language,
                "refund": 1 if for_payouts else 0,
                "description": description,
            },
        )

    def register_card_and_pay(
        self,
        amount: Amount,
        order_id: str,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
        success_redirect_url: str | None = None,
        error_redirect_url: str | None = None,
    ) -> Response:
        """Charge the customer and register the card in one step."""
        return self._post(
            "/api/1/card-registration-with-pay",
            {
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "description": description,
                **self._redirects(success_redirect_url, error_redirect_url),
            },
        )

    def charge_saved_card(
        self,
        card_id: str,
        amount: Amount,
        order_id: str,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
    ) -> Response:
        """Charge a card the customer registered earlier."""
        return self._post(
            "/api/1/execute-pay",
            {
                "card_id": card_id,
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "description": description,
            },
        )

    def get_card_status(self, card_id: str) -> Response:
        """Look up a saved card by its id."""
        return self._post("/api/1/get-status-card", {"card_id": card_id})

    def refund(
        self,
        card_id: str,
        amount: Amount,
        order_id: str,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
    ) -> Response:
        """Refund to a saved card, or pay out if the card was registered for payouts."""
        return self._post(
            "/api/1/refund-request",
            {
                "card_id": card_id,
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "description": description,
            },
        )

    def reverse(
        self,
        transaction: str,
        *,
        amount: Amount | None = None,
        language: str | None = None,
        currency: str | None = None,
    ) -> Response:
        """Cancel a settled payment, in full or in part."""
        return self._post(
            "/api/1/reverse",
            {
                "transaction": transaction,
                "amount": _money(amount) if amount is not None else None,
                "currency": currency or self.currency,
                "language": language or self.language,
            },
        )

    def get_installment_plans(
        self,
        order_id: str,
        *,
        amount: Amount | None = None,
        language: str | None = None,
        currency: str | None = None,
    ) -> list[dict[str, Any]]:
        """List the installment plans available for an order."""
        result = self._post_raw(
            "/api/1/get-installment-request",
            {
                "order_id": order_id,
                "amount": _money(amount) if amount is not None else None,
                "currency": currency or self.currency,
                "language": language or self.language,
            },
        )
        return list(result) if isinstance(result, list) else []

    def pay_by_installment(
        self,
        amount: Amount,
        order_id: str,
        installment_card_id: str,
        installment_month: int,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
        success_redirect_url: str | None = None,
        error_redirect_url: str | None = None,
    ) -> Response:
        """Start an installment payment on a chosen plan."""
        return self._post(
            "/api/1/installment-request",
            {
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "installment_card_id": installment_card_id,
                "installment_month": installment_month,
                "description": description,
                **self._redirects(success_redirect_url, error_redirect_url),
            },
        )

    def list_wallets(self) -> dict[str, str]:
        """List the digital wallets available on the account."""
        result = self._post_raw("/api/1/wallet/status", {})
        return dict(result) if isinstance(result, dict) else {}

    def pay_with_wallet(
        self,
        wallet_id: str,
        amount: Amount,
        order_id: str,
        *,
        description: str | None = None,
        language: str | None = None,
        currency: str | None = None,
    ) -> Response:
        """Start a payment through a digital wallet."""
        return self._post(
            "/api/1/wallet/payment",
            {
                "wallet_id": wallet_id,
                "amount": _money(amount),
                "currency": currency or self.currency,
                "language": language or self.language,
                "order_id": order_id,
                "description": description,
            },
        )

    def create_widget(self, amount: Amount, order_id: str, description: str) -> Response:
        """Create an Apple Pay and Google Pay widget URL to embed in an iframe."""
        return self._post(
            "/api/1/token/widget",
            {"amount": _money(amount), "order_id": order_id, "description": description},
        )

    def create_invoice(
        self,
        amount: Amount,
        period_from: str,
        period_to: str,
        *,
        name: str | None = None,
        description: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        tin: str | None = None,
        contract_number: str | None = None,
        merchant_order_id: str | None = None,
        display: bool = True,
        save_as_template: bool = False,
        allow_installment: bool = False,
    ) -> Response:
        """Create a pay-by-link invoice."""
        return self._post(
            "/api/1/invoices/create",
            {
                "sum": _money(amount),
                "period_from": period_from,
                "period_to": period_to,
                "name": name,
                "description": description,
                "phone": phone,
                "email": email,
                "inn": tin,
                "contract_number": contract_number,
                "merchant_order_id": merchant_order_id,
                "display": 1 if display else 0,
                "save_as_template": 1 if save_as_template else 0,
                "status_installment": 1 if allow_installment else 0,
            },
        )

    def update_invoice(
        self,
        invoice_id: int,
        amount: Amount,
        period_from: str,
        period_to: str,
        *,
        name: str | None = None,
        description: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        display: bool = True,
        save_as_template: bool = False,
        allow_installment: bool = False,
    ) -> Response:
        """Update an invoice that is still waiting for payment."""
        return self._post(
            "/api/1/invoices/update",
            {
                "id": invoice_id,
                "sum": _money(amount),
                "period_from": period_from,
                "period_to": period_to,
                "name": name,
                "description": description,
                "phone": phone,
                "email": email,
                "display": 1 if display else 0,
                "save_as_template": 1 if save_as_template else 0,
                "status_installment": 1 if allow_installment else 0,
            },
        )

    def get_invoice(self, invoice_id: int) -> Response:
        """Look up an invoice by its id."""
        return self._post("/api/1/invoices/view", {"id": invoice_id})

    def list_invoices(self, *, kind: str | None = None, order: str | None = None) -> Response:
        """List invoices on the account."""
        return self._post("/api/1/invoices/list", {"type": kind, "order": order})

    def send_invoice_sms(self, invoice_id: int, phone: str) -> Response:
        """Send an invoice to a phone number by SMS."""
        return self._post("/api/1/invoices/send-sms", {"id": invoice_id, "phone": phone})

    def send_invoice_email(self, invoice_id: int, email: str) -> Response:
        """Send an invoice to an email address."""
        return self._post("/api/1/invoices/send-email", {"id": invoice_id, "email": email})

    def create_bank_transfer(
        self,
        order_id: str,
        amount: Amount,
        description: str,
        iban: str,
        name: str,
        tin: str,
        bank_code: str,
        *,
        bank_name: str | None = None,
        email: str | None = None,
        address: str | None = None,
        additional_info: str | None = None,
        webhook_url: str | None = None,
    ) -> Response:
        """Send a B2B bank transfer to an IBAN."""
        return self._post_json(
            "/api/1/b2b/payment",
            {
                "order_id": order_id,
                "amount": _money(amount),
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

    def get_bank_transfer(self, order_id: str) -> Response:
        """Look up a B2B bank transfer by its order id."""
        status, body = self._send("GET", f"/api/1/b2b/payment/{order_id}")
        return _transport.parse(status, body)

    def heartbeat(self) -> Response:
        """Check that the gateway is reachable."""
        status, body = self._send("GET", "/api/heartbeat")
        return _transport.parse(status, body)

    def verify_callback(self, data: str, signature: str) -> Callback:
        """Verify a callback's signature and return its decoded payload."""
        return verify_callback(self.private_key, data, signature)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> EpointClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
