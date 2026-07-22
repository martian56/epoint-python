from __future__ import annotations

import os
from types import TracebackType
from typing import Any

import httpx

from . import _endpoints as ep
from . import _transport
from ._endpoints import Amount, Defaults
from .callbacks import verify_callback
from .client import PRODUCTION_URL
from .enums import Currency, Language
from .errors import TransportError
from .models import Callback, Response


class AsyncEpointClient:
    def __init__(
        self,
        public_key: str,
        private_key: str,
        *,
        base_url: str = PRODUCTION_URL,
        language: str = Language.AZ,
        currency: str = Currency.AZN,
        success_redirect_url: str | None = None,
        error_redirect_url: str | None = None,
        timeout: float = 30.0,
        transport: httpx.AsyncClient | None = None,
    ) -> None:
        self.public_key = public_key
        self.private_key = private_key
        self.base_url = base_url.rstrip("/")
        self.language = language
        self.currency = currency
        self.success_redirect_url = success_redirect_url
        self.error_redirect_url = error_redirect_url
        self._http = transport or httpx.AsyncClient(timeout=timeout)

    @classmethod
    def from_env(cls, **overrides: Any) -> AsyncEpointClient:
        params: dict[str, Any] = {
            "base_url": os.environ.get("EPOINT_BASE_URL", PRODUCTION_URL),
            "language": os.environ.get("EPOINT_LANGUAGE", Language.AZ),
            "success_redirect_url": os.environ.get("EPOINT_SUCCESS_REDIRECT_URL"),
            "error_redirect_url": os.environ.get("EPOINT_FAILED_REDIRECT_URL"),
        }
        params.update(overrides)
        return cls(os.environ["EPOINT_PUBLIC_KEY"], os.environ["EPOINT_PRIVATE_KEY"], **params)

    @property
    def _defaults(self) -> Defaults:
        return Defaults(
            self.language, self.currency, self.success_redirect_url, self.error_redirect_url
        )

    async def _send(self, method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
        try:
            response = await self._http.request(method, f"{self.base_url}{path}", **kwargs)
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

    async def _post(self, path: str, payload: dict[str, Any]) -> Response:
        form = _transport.build_form(self.public_key, self.private_key, payload)
        return _transport.parse(*await self._send("POST", path, data=form))

    async def _post_raw(self, path: str, payload: dict[str, Any]) -> Any:
        form = _transport.build_form(self.public_key, self.private_key, payload)
        status, body = await self._send("POST", path, data=form)
        if isinstance(body, dict):
            _transport.parse(status, body)
        return body

    async def _post_json(self, path: str, payload: dict[str, Any]) -> Response:
        form = _transport.build_json(self.public_key, self.private_key, payload)
        return _transport.parse(*await self._send("POST", path, json=form))

    async def create_payment(
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
        return await self._post(
            *ep.create_payment(
                self._defaults,
                amount,
                order_id,
                description,
                language,
                currency,
                success_redirect_url,
                error_redirect_url,
                other_attr,
            )
        )

    async def create_payment_request(
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
        return await self._post(
            *ep.create_payment_request(
                self._defaults,
                amount,
                order_id,
                description,
                language,
                currency,
                success_redirect_url,
                error_redirect_url,
                other_attr,
            )
        )

    async def create_amex_payment(
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
        return await self._post(
            *ep.create_amex_payment(
                self._defaults,
                amount,
                order_id,
                description,
                language,
                currency,
                success_redirect_url,
                error_redirect_url,
                other_attr,
            )
        )

    async def change_payment_sum(
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
        return await self._post(
            *ep.change_payment_sum(
                self._defaults,
                amount,
                order_id,
                description,
                language,
                currency,
                success_redirect_url,
                error_redirect_url,
                other_attr,
            )
        )

    async def reserve(
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
        return await self._post(
            *ep.reserve(
                self._defaults,
                amount,
                order_id,
                description,
                language,
                currency,
                success_redirect_url,
                error_redirect_url,
                other_attr,
            )
        )

    async def capture(self, transaction: str, amount: Amount) -> Response:
        """Capture a previously reserved amount, in full or in part."""
        return await self._post(*ep.capture(transaction, amount))

    async def get_status(self, transaction: str) -> Response:
        """Look up a transaction by its epoint id."""
        return await self._post(*ep.get_status(transaction))

    async def get_card_status(self, card_id: str) -> Response:
        """Look up a saved card by its id."""
        return await self._post(*ep.get_card_status(card_id))

    async def create_split_payment(
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
        return await self._post(
            *ep.create_split_payment(
                self._defaults,
                amount,
                order_id,
                split_account,
                split_amount,
                description,
                language,
                currency,
                success_redirect_url,
                error_redirect_url,
                other_attr,
            )
        )

    async def split_charge_saved_card(
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
        return await self._post(
            *ep.split_charge_saved_card(
                self._defaults,
                card_id,
                amount,
                order_id,
                split_account,
                split_amount,
                description,
                language,
                currency,
            )
        )

    async def register_card(
        self,
        *,
        description: str | None = None,
        language: str | None = None,
        for_payouts: bool = False,
    ) -> Response:
        """Start card registration. The customer confirms it on the checkout page."""
        return await self._post(
            *ep.register_card(self._defaults, description, language, for_payouts)
        )

    async def register_card_and_pay(
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
        return await self._post(
            *ep.register_card_and_pay(
                self._defaults,
                amount,
                order_id,
                description,
                language,
                currency,
                success_redirect_url,
                error_redirect_url,
            )
        )

    async def charge_saved_card(
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
        return await self._post(
            *ep.charge_saved_card(
                self._defaults,
                card_id,
                amount,
                order_id,
                description,
                language,
                currency,
            )
        )

    async def refund(
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
        return await self._post(
            *ep.refund(
                self._defaults,
                card_id,
                amount,
                order_id,
                description,
                language,
                currency,
            )
        )

    async def reverse(
        self,
        transaction: str,
        *,
        amount: Amount | None = None,
        language: str | None = None,
        currency: str | None = None,
    ) -> Response:
        """Cancel a settled payment, in full or in part."""
        return await self._post(
            *ep.reverse(self._defaults, transaction, amount, language, currency)
        )

    async def get_installment_plans(
        self,
        order_id: str,
        *,
        amount: Amount | None = None,
        language: str | None = None,
        currency: str | None = None,
    ) -> list[dict[str, Any]]:
        """List the installment plans available for an order."""
        result = await self._post_raw(
            *ep.get_installment_plans(self._defaults, order_id, amount, language, currency)
        )
        return list(result) if isinstance(result, list) else []

    async def pay_by_installment(
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
        return await self._post(
            *ep.pay_by_installment(
                self._defaults,
                amount,
                order_id,
                installment_card_id,
                installment_month,
                description,
                language,
                currency,
                success_redirect_url,
                error_redirect_url,
            )
        )

    async def list_wallets(self) -> dict[str, str]:
        """List the digital wallets available on the account."""
        result = await self._post_raw("/api/1/wallet/status", {})
        return dict(result) if isinstance(result, dict) else {}

    async def pay_with_wallet(
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
        return await self._post(
            *ep.pay_with_wallet(
                self._defaults,
                wallet_id,
                amount,
                order_id,
                description,
                language,
                currency,
            )
        )

    async def create_widget(self, amount: Amount, order_id: str, description: str) -> Response:
        """Create an Apple Pay and Google Pay widget URL to embed in an iframe."""
        return await self._post(*ep.create_widget(amount, order_id, description))

    async def create_invoice(
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
        return await self._post(
            *ep.create_invoice(
                amount,
                period_from,
                period_to,
                name,
                description,
                phone,
                email,
                tin,
                contract_number,
                merchant_order_id,
                display,
                save_as_template,
                allow_installment,
            )
        )

    async def update_invoice(
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
        return await self._post(
            *ep.update_invoice(
                invoice_id,
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
            )
        )

    async def get_invoice(self, invoice_id: int) -> Response:
        """Look up an invoice by its id."""
        return await self._post(*ep.get_invoice(invoice_id))

    async def list_invoices(self, *, kind: str | None = None, order: str | None = None) -> Response:
        """List invoices on the account."""
        return await self._post(*ep.list_invoices(kind, order))

    async def send_invoice_sms(self, invoice_id: int, phone: str) -> Response:
        """Send an invoice to a phone number by SMS."""
        return await self._post(*ep.send_invoice_sms(invoice_id, phone))

    async def send_invoice_email(self, invoice_id: int, email: str) -> Response:
        """Send an invoice to an email address."""
        return await self._post(*ep.send_invoice_email(invoice_id, email))

    async def create_bank_transfer(
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
        return await self._post_json(
            *ep.create_bank_transfer(
                order_id,
                amount,
                description,
                iban,
                name,
                tin,
                bank_code,
                bank_name,
                email,
                address,
                additional_info,
                webhook_url,
            )
        )

    async def get_bank_transfer(self, order_id: str) -> Response:
        """Look up a B2B bank transfer by its order id."""
        return _transport.parse(*await self._send("GET", f"/api/1/b2b/payment/{order_id}"))

    async def heartbeat(self) -> Response:
        """Check that the gateway is reachable."""
        return _transport.parse(*await self._send("GET", "/api/heartbeat"))

    def verify_callback(self, data: str, signature: str) -> Callback:
        """Verify a callback's signature and return its decoded payload."""
        return verify_callback(self.private_key, data, signature)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncEpointClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
