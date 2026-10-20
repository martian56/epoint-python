import base64
import json
import os
import uuid
from typing import Any

import httpx
import pytest

from epoint import AsyncEpointClient, GatewayError
from epoint._signing import matches

PUBLIC_KEY = "i000000001"
PRIVATE_KEY = "sandbox_private_key_0000000001"
SANDBOX_URL = os.environ.get("EPOINT_BASE_URL", "http://localhost:8181")


def async_client_with(handler) -> AsyncEpointClient:
    transport = httpx.MockTransport(handler)
    return AsyncEpointClient(
        PUBLIC_KEY,
        PRIVATE_KEY,
        base_url="https://epoint.test",
        transport=httpx.AsyncClient(transport=transport),
    )


async def test_request_is_signed_and_parsed():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        form = httpx.QueryParams(request.content.decode())
        seen["payload"] = json.loads(base64.b64decode(form["data"]))
        return httpx.Response(200, json={"status": "success", "transaction": "te1"})

    async with async_client_with(handler) as client:
        result = await client.create_payment(amount=12.5, order_id="a-1")

    assert result.ok
    assert result.transaction == "te1"
    assert seen["payload"]["amount"] == "12.50"


async def test_card_registration_sends_the_redirect_urls():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        form = httpx.QueryParams(request.content.decode())
        seen["payload"] = json.loads(base64.b64decode(form["data"]))
        return httpx.Response(200, json={"status": "success", "card_id": "ce1"})

    async with async_client_with(handler) as client:
        result = await client.register_card(
            description="async",
            success_redirect_url="https://shop.test/ok",
            error_redirect_url="https://shop.test/fail",
        )

    assert result["card_id"] == "ce1"
    assert seen["payload"]["success_redirect_url"] == "https://shop.test/ok"
    assert seen["payload"]["error_redirect_url"] == "https://shop.test/fail"


async def test_error_status_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "error", "message": "bad", "code": "100"})

    async with async_client_with(handler) as client:
        with pytest.raises(GatewayError):
            await client.get_status("te1")


async def test_failed_status_is_returned():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "failed", "code": "116"})

    async with async_client_with(handler) as client:
        result = await client.get_status("te1")

    assert not result.ok
    assert result.get("code") == "116"


def async_recording_client(seen: dict, response: Any = None) -> AsyncEpointClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.clear()
        seen["path"] = request.url.path
        if request.headers.get("content-type", "").startswith("application/json"):
            body = json.loads(request.content)
            seen["payload"] = json.loads(base64.b64decode(body["data"]))
        else:
            form = httpx.QueryParams(request.content.decode())
            seen["payload"] = json.loads(base64.b64decode(form["data"]))
        return httpx.Response(200, json={"status": "success"} if response is None else response)

    return AsyncEpointClient(
        PUBLIC_KEY,
        PRIVATE_KEY,
        base_url="https://epoint.test",
        success_redirect_url="https://shop.test/default-ok",
        error_redirect_url="https://shop.test/default-fail",
        transport=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


async def test_get_status_returns_a_payment_that_ended_in_error_async():
    body = {
        "status": "error",
        "code": "",
        "message": "An error occurred during payment",
        "transaction": "te1",
    }

    async with async_client_with(lambda request: httpx.Response(200, json=body)) as client:
        result = await client.get_status("te1")

    assert result.status == "error"
    assert result.transaction == "te1"
    assert not result.ok


async def test_get_status_still_raises_on_a_non_2xx_error_async():
    body = {"status": "error", "message": "denied", "transaction": "te1"}

    async with async_client_with(lambda request: httpx.Response(403, json=body)) as client:
        with pytest.raises(GatewayError):
            await client.get_status("te1")


async def test_other_calls_still_raise_on_error_with_a_transaction_async():
    body = {"status": "error", "message": "bad", "transaction": "te1"}

    async with async_client_with(lambda request: httpx.Response(200, json=body)) as client:
        with pytest.raises(GatewayError):
            await client.create_payment(1, "o")


async def test_ok_and_typed_fields_async():
    body = {"status": "SUCCESS", "order_id": "b1", "trace_id": "tr1", "amount": "1250.00"}

    async with async_client_with(lambda request: httpx.Response(200, json=body)) as client:
        result = await client.get_bank_transfer("b1")

    assert result.ok
    assert result.order_id == "b1"
    assert result.trace_id == "tr1"
    assert result.amount == 1250.0


async def test_token_split_payment_payload_async():
    seen: dict = {}
    async with async_recording_client(seen) as client:
        await client.create_token_split_payment(
            amount=100, order_id="o-1", split_account="i000000002", split_amount=30
        )

    assert seen["path"] == "/api/1/token/split-payment"
    payload = seen["payload"]
    assert payload["amount"] == "100.00"
    assert payload["split_user"] == "i000000002"
    assert payload["split_amount"] == "30.00"
    assert payload["currency"] == "AZN"
    assert payload["order_id"] == "o-1"
    assert payload["success_redirect_url"] == "https://shop.test/default-ok"
    assert payload["error_redirect_url"] == "https://shop.test/default-fail"


async def test_checkout_form_is_signed_and_makes_no_request_async():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("checkout_form must not send a request")

    async with AsyncEpointClient(
        PUBLIC_KEY,
        PRIVATE_KEY,
        base_url="https://epoint.test",
        transport=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    ) as client:
        form = client.checkout_form(amount=5, order_id="o-1", is_installment=False)

    assert form.url == "https://epoint.test/api/1/checkout"
    assert matches(PRIVATE_KEY, form.data, form.signature)
    payload = json.loads(base64.b64decode(form.data))
    assert payload == {
        "public_key": PUBLIC_KEY,
        "amount": "5.00",
        "currency": "AZN",
        "language": "az",
        "order_id": "o-1",
        "is_installment": 0,
    }


@pytest.mark.parametrize(("value", "sent"), [(True, 1), (False, 0), (None, None)])
async def test_is_installment_is_sent_as_an_integer_or_omitted_async(value, sent):
    seen: dict = {}
    async with async_recording_client(seen) as client:
        for call, path in (
            (client.create_payment, "/api/1/request"),
            (client.create_payment_request, "/api/1/payment-request"),
        ):
            await call(amount=1, order_id="o", is_installment=value)
            assert seen["path"] == path
            assert seen["payload"].get("is_installment") == sent
            assert ("is_installment" in seen["payload"]) == (value is not None)


async def test_new_optional_parameters_async():
    seen: dict = {}
    async with async_recording_client(seen) as client:
        await client.create_bank_transfer(
            order_id="b1",
            amount=100,
            description="fees",
            iban="AZ21NABZ00000000137010001944",
            name="ACME",
            tin="1234567892",
            bank_code="505141",
            bulk_description="July payroll",
        )
        assert seen["payload"]["bulk_description"] == "July payroll"

        await client.pay_by_installment(
            amount=200,
            order_id="o",
            installment_card_id="kapital",
            installment_month=6,
            other_attr={"k": "v"},
        )
        assert seen["path"] == "/api/1/installment-request"
        assert seen["payload"]["other_attr"] == {"k": "v"}

        await client.update_invoice(
            7,
            amount=11,
            period_from="2026-01-01",
            period_to="2026-12-31",
            tin="1234567892",
            contract_number="C-1",
            merchant_order_id="M-1",
        )
        assert seen["payload"]["inn"] == "1234567892"
        assert seen["payload"]["contract_number"] == "C-1"
        assert seen["payload"]["merchant_order_id"] == "M-1"

    async with async_recording_client(seen, []) as client:
        plans = await client.get_installment_plans(
            order_id="o", amount=200, description="sofa", other_attr={"k": "v"}
        )
    assert plans == []
    assert seen["payload"]["description"] == "sofa"
    assert seen["payload"]["other_attr"] == {"k": "v"}


def sandbox_up() -> bool:
    try:
        return httpx.get(f"{SANDBOX_URL}/api/heartbeat", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def pay(redirect_url: str, card: str = "4111111111111111") -> None:
    token = redirect_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
    httpx.post(
        f"{SANDBOX_URL}/checkout/{token}",
        data={"card_number": card, "card_holder": "TESTER", "month": "12", "year": "30"},
    )


@pytest.mark.sandbox
async def test_payment_end_to_end_async():
    if not sandbox_up():
        pytest.skip(f"no sandbox on {SANDBOX_URL}")

    async with AsyncEpointClient(
        PUBLIC_KEY, PRIVATE_KEY, base_url=SANDBOX_URL, language="en"
    ) as client:
        assert (await client.heartbeat()).get("status") == "ok"

        created = await client.create_payment(amount=25.5, order_id=f"aio-{uuid.uuid4().hex[:10]}")
        assert created.redirect_url
        pay(created.redirect_url)

        status = await client.get_status(created.transaction)
        assert status.status == "success"
        assert status.get("card_mask") == "411111******1111"


@pytest.mark.sandbox
async def test_new_features_against_the_sandbox_async():
    if not sandbox_up():
        pytest.skip(f"no sandbox on {SANDBOX_URL}")

    httpx.patch(
        f"{SANDBOX_URL}/_sandbox/merchants/{PUBLIC_KEY}",
        json={"token_payments_enabled": True},
    )

    async with AsyncEpointClient(
        PUBLIC_KEY, PRIVATE_KEY, base_url=SANDBOX_URL, language="en"
    ) as client:
        assert (await client.heartbeat()).ok

        errored = await client.create_payment(amount=5, order_id=f"aio-{uuid.uuid4().hex[:10]}")
        pay(errored.redirect_url, card="4000000000009998")
        status = await client.get_status(errored.transaction)
        assert status.status == "error"
        assert status.message == "An error occurred during payment"
        assert not status.ok

        with pytest.raises(GatewayError):
            await client.get_status("te9999999999")

        split = await client.create_token_split_payment(
            amount=100,
            order_id=f"aio-{uuid.uuid4().hex[:10]}",
            split_account="i000000002",
            split_amount=30,
        )
        assert split.redirect_url
        assert split.transaction
        pay(split.redirect_url)
        assert (await client.get_status(split.transaction)).status == "success"

        with pytest.raises(GatewayError):
            await client.create_token_split_payment(
                amount=100,
                order_id=f"aio-{uuid.uuid4().hex[:10]}",
                split_account="i000009999",
                split_amount=30,
            )

        order_id = f"aio-{uuid.uuid4().hex[:10]}"
        form = client.checkout_form(amount=7, order_id=order_id)
        async with httpx.AsyncClient() as http:
            answer = await http.post(form.url, data=form.fields, follow_redirects=False)
            assert answer.status_code == 303
            pay(answer.headers["location"])
            rows = (
                await http.get(
                    f"{SANDBOX_URL}/_sandbox/transactions",
                    params={"merchant": PUBLIC_KEY, "limit": 200},
                )
            ).json()
        transaction = next(row["transaction"] for row in rows if row["order_id"] == order_id)
        assert (await client.get_status(transaction)).status == "success"

        invoice = await client.create_invoice(
            amount=10, period_from="2026-01-01", period_to="2026-12-31"
        )
        await client.update_invoice(
            invoice["id"],
            amount=11,
            period_from="2026-01-01",
            period_to="2026-12-31",
            tin="1234567892",
            contract_number="C-88",
            merchant_order_id="M-88",
        )
        viewed = (await client.get_invoice(invoice["id"]))["invoice"]
        assert viewed["inn"] == "1234567892"
        assert viewed["contract_number"] == "C-88"
        assert viewed["merchant_order_id"] == "M-88"
