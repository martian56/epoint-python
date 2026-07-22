import uuid

import httpx
import pytest

from epoint import CardStatus, EpointClient, GatewayError, Status

pytestmark = pytest.mark.sandbox

SANDBOX_URL = "http://localhost:8181"
PARTNER_KEY = "i000000002"


def order() -> str:
    return f"py-{uuid.uuid4().hex[:12]}"


def grant_all(client: EpointClient) -> None:
    httpx.patch(
        f"{client.base_url}/_sandbox/merchants/{client.public_key}",
        json={
            "amex_enabled": True,
            "token_payments_enabled": True,
            "installments_enabled": True,
            "wallets_enabled": True,
            "b2b_enabled": True,
        },
    )


def test_heartbeat(client):
    assert client.heartbeat().get("status") == "ok"


def test_payment_end_to_end(client, pay):
    created = client.create_payment(amount=25.50, order_id=order(), description="Kilim")
    assert created.ok
    assert created.redirect_url

    pay(client, created.redirect_url)
    status = client.get_status(created.transaction)
    assert status.status == "success"
    assert status.get("code") == "000"
    assert status.get("card_mask") == "411111******1111"


def test_declined_card_reports_the_bank_code(client, pay):
    created = client.create_payment(amount=10, order_id=order())
    pay(client, created.redirect_url, card="4000000000000116")
    status = client.get_status(created.transaction)
    assert status.status == "failed"
    assert status.get("code") == "116"


def test_saved_card_can_be_charged(client, pay):
    registration = client.register_card(description="repeat")
    assert registration.get("card_id")
    pay(client, registration.redirect_url)

    card_status = client.get_card_status(registration["card_id"])
    assert card_status.get("status") == "active"

    charge = client.charge_saved_card(registration["card_id"], amount=15, order_id=order())
    assert charge.get("bank_response") == "000"


def test_reverse_returns_the_payment(client, pay):
    created = client.create_payment(amount=40, order_id=order())
    pay(client, created.redirect_url)
    reversed_result = client.reverse(created.transaction)
    assert reversed_result.ok


def test_split_payment(client, pay):
    created = client.create_split_payment(
        amount=100, order_id=order(), split_account=PARTNER_KEY, split_amount=30
    )
    assert created.ok
    pay(client, created.redirect_url)
    assert client.get_status(created.transaction).status == "success"


def test_ungranted_feature_is_refused(client):
    httpx.patch(
        f"{client.base_url}/_sandbox/merchants/{client.public_key}",
        json={"wallets_enabled": False},
    )
    with pytest.raises(GatewayError):
        client.pay_with_wallet("wallet_epul", amount=10, order_id=order())


def test_wallets_and_installments(client):
    grant_all(client)

    wallets = client.list_wallets()
    assert isinstance(wallets, dict)
    assert wallets

    plans = client.get_installment_plans(order_id=order(), amount=200)
    assert isinstance(plans, list)
    assert plans
    assert "installment_card_id" in plans[0]


def test_widget_returns_an_embeddable_url(client):
    grant_all(client)
    widget = client.create_widget(amount=50, order_id=order(), description="wallet")
    assert "widget=1" in widget.get("widget_url", "")


def test_invoice_lifecycle(client):
    created = client.create_invoice(
        amount=49.90,
        period_from="2026-01-01",
        period_to="2026-12-31",
        name="Leyla",
        description="deposit",
        phone="+994501234567",
        email="leyla@example.com",
    )
    invoice_id = created["id"]
    assert client.get_invoice(invoice_id).ok
    assert client.send_invoice_sms(invoice_id, "+994501234567").ok
    assert client.send_invoice_email(invoice_id, "leyla@example.com").ok


def test_bank_transfer(client):
    grant_all(client)
    order_id = order()
    created = client.create_bank_transfer(
        order_id=order_id,
        amount=1250,
        description="July fees",
        iban="AZ21NABZ00000000137010001944",
        name="Logistika MMC",
        tin="1234567892",
        bank_code="505141",
    )
    assert created.ok
    assert client.get_bank_transfer(order_id).get("order_id") == order_id


def test_missing_required_field_is_refused(client):
    with pytest.raises(GatewayError) as info:
        client._post("/api/1/request", {"amount": "10.00", "currency": "AZN"})
    assert "order_id" in str(info.value)


def test_the_statuses_the_sandbox_returns_are_all_in_the_enum(client, pay):
    """Guards against the enum drifting away from what the API actually sends."""
    paid = client.create_payment(amount=5, order_id=order())
    pay(client, paid.redirect_url)

    declined = client.create_payment(amount=5, order_id=order())
    pay(client, declined.redirect_url, card="4000000000000116")

    seen = {
        client.get_status(paid.transaction).status,
        client.get_status(declined.transaction).status,
    }
    assert seen == {Status.SUCCESS, Status.FAILED}
    assert all(s in set(Status) for s in seen)


def test_a_card_status_from_the_sandbox_is_in_the_enum(client, pay):
    registered = client.register_card(description="enum check")
    pay(client, registered.redirect_url)

    card = client.get_card_status(registered["card_id"])
    assert card.get("status") == CardStatus.ACTIVE
    assert card.get("status") in set(CardStatus)
