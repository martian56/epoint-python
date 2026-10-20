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


def test_card_registration_returns_the_customer_to_the_given_urls(client):
    approved = client.register_card(
        description="redirect check",
        success_redirect_url="https://shop.test/card-ok",
        error_redirect_url="https://shop.test/card-fail",
    )
    declined = client.register_card(
        description="redirect check",
        success_redirect_url="https://shop.test/card-ok",
        error_redirect_url="https://shop.test/card-fail",
    )

    def submit(redirect_url: str, card: str) -> httpx.Response:
        token = redirect_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
        return httpx.post(
            f"{SANDBOX_URL}/checkout/{token}",
            data={"card_number": card, "card_holder": "TESTER", "month": "12", "year": "30"},
            follow_redirects=False,
        )

    ok = submit(approved.redirect_url, "4111111111111111")
    failed = submit(declined.redirect_url, "4000000000000116")

    assert ok.status_code == 303
    assert ok.headers["location"] == "https://shop.test/card-ok"
    assert failed.status_code == 303
    assert failed.headers["location"] == "https://shop.test/card-fail"
    assert client.get_card_status(approved["card_id"]).get("status") == CardStatus.ACTIVE


def enable_token_payments(client: EpointClient) -> None:
    httpx.patch(
        f"{client.base_url}/_sandbox/merchants/{client.public_key}",
        json={"token_payments_enabled": True},
    )


def transaction_for(client: EpointClient, order_id: str) -> str:
    rows = httpx.get(
        f"{client.base_url}/_sandbox/transactions",
        params={"merchant": client.public_key, "limit": 200},
    ).json()
    return next(row["transaction"] for row in rows if row["order_id"] == order_id)


def test_a_payment_that_ended_in_error_reads_back_without_raising(client, pay):
    created = client.create_payment(amount=5, order_id=order())
    pay(client, created.redirect_url, card="4000000000009998")

    status = client.get_status(created.transaction)
    assert status.status == Status.ERROR
    assert status.message == "An error occurred during payment"
    assert status.code == ""
    assert status.transaction == created.transaction
    assert not status.ok


def test_an_unknown_transaction_still_raises(client):
    with pytest.raises(GatewayError):
        client.get_status("te9999999999")


def test_server_error_and_returned_read_back(client, pay):
    timed_out = client.create_payment(amount=5, order_id=order())
    pay(client, timed_out.redirect_url, card="4000000000009999")
    server_error = client.get_status(timed_out.transaction)
    assert server_error.status == Status.SERVER_ERROR
    assert not server_error.ok

    paid = client.create_payment(amount=5, order_id=order())
    pay(client, paid.redirect_url)
    client.reverse(paid.transaction)
    returned = client.get_status(paid.transaction)
    assert returned.status == Status.RETURNED
    assert not returned.ok


def test_typed_fields_read_from_a_settled_payment(client, pay):
    order_id = order()
    created = client.create_payment(amount=25.5, order_id=order_id)
    assert created.trace_id
    pay(client, created.redirect_url)

    status = client.get_status(created.transaction)
    assert status.ok
    assert status.code == "000"
    assert status.bank_response == "000"
    assert status.bank_transaction
    assert status.operation_code == "100"
    assert status.rrn
    assert status.card_mask == "411111******1111"
    assert status.card_name == "TESTER"
    assert status.amount == 25.5
    assert status.trace_id


def test_token_split_payment(client, pay):
    enable_token_payments(client)
    created = client.create_token_split_payment(
        amount=100, order_id=order(), split_account=PARTNER_KEY, split_amount=30
    )
    assert created.ok
    assert created.redirect_url
    assert created.transaction
    assert created.trace_id

    pay(client, created.redirect_url)
    assert client.get_status(created.transaction).status == Status.SUCCESS


def test_token_split_payment_with_an_unknown_split_user_is_refused(client):
    enable_token_payments(client)
    with pytest.raises(GatewayError) as info:
        client.create_token_split_payment(
            amount=100, order_id=order(), split_account="i000009999", split_amount=30
        )
    assert "split_user" in str(info.value)


def test_checkout_form_posts_to_the_card_page(client, pay):
    order_id = order()
    form = client.checkout_form(amount=12.5, order_id=order_id, is_installment=False)
    assert form.url == f"{SANDBOX_URL}/api/1/checkout"

    answer = httpx.post(form.url, data=form.fields, follow_redirects=False)
    assert answer.status_code == 303
    location = answer.headers["location"]
    assert "/checkout/" in location

    pay(client, location)
    status = client.get_status(transaction_for(client, order_id))
    assert status.status == Status.SUCCESS
    assert status.amount == 12.5


def test_updated_invoice_keeps_tin_contract_and_merchant_order(client):
    created = client.create_invoice(amount=10, period_from="2026-01-01", period_to="2026-12-31")
    invoice_id = created["id"]
    updated = client.update_invoice(
        invoice_id,
        amount=11,
        period_from="2026-01-01",
        period_to="2026-12-31",
        tin="1234567892",
        contract_number="C-77",
        merchant_order_id="M-77",
    )
    assert updated.ok

    invoice = client.get_invoice(invoice_id)["invoice"]
    assert invoice["inn"] == "1234567892"
    assert invoice["contract_number"] == "C-77"
    assert invoice["merchant_order_id"] == "M-77"


def test_new_optional_parameters_are_accepted(client, pay):
    grant_all(client)
    plans = client.get_installment_plans(
        order_id=order(), amount=200, description="sofa", other_attr={"k": "v"}
    )
    assert plans

    request = client.create_payment_request(amount=5, order_id=order(), is_installment=True)
    assert request.redirect_url

    transfer = client.create_bank_transfer(
        order_id=order(),
        amount=100,
        description="fees",
        iban="AZ21NABZ00000000137010001944",
        name="Logistika MMC",
        tin="1234567892",
        bank_code="505141",
        bulk_description="July payroll",
    )
    assert transfer.ok
