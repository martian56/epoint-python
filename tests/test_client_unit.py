import base64
import json
from typing import Any

import httpx
import pytest

from epoint import EpointClient, GatewayError, TransportError
from epoint._signing import matches

PUBLIC_KEY = "i000000001"
PRIVATE_KEY = "sandbox_private_key_0000000001"


def decode_sent(request: httpx.Request) -> tuple[dict, httpx.QueryParams]:
    form = httpx.QueryParams(request.content.decode())
    return json.loads(base64.b64decode(form["data"])), form


def client_with(handler) -> EpointClient:
    transport = httpx.MockTransport(handler)
    return EpointClient(
        PUBLIC_KEY,
        PRIVATE_KEY,
        base_url="https://epoint.test",
        transport=httpx.Client(transport=transport),
    )


def test_request_carries_a_valid_signature():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload, form = decode_sent(request)
        captured["payload"] = payload
        captured["signed"] = matches(PRIVATE_KEY, form["data"], form["signature"])
        return httpx.Response(200, json={"status": "success", "transaction": "te1"})

    client = client_with(handler)
    result = client.create_payment(amount=30.75, order_id="order-1")

    assert result.ok
    assert captured["signed"]
    assert captured["payload"]["public_key"] == PUBLIC_KEY
    assert captured["payload"]["amount"] == "30.75"
    assert captured["payload"]["order_id"] == "order-1"


def test_amounts_are_formatted_to_two_places():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload, _ = decode_sent(request)
        seen.update(payload)
        return httpx.Response(200, json={"status": "success"})

    client_with(handler).create_payment(amount=5, order_id="o")
    assert seen["amount"] == "5.00"


def test_none_fields_are_dropped_from_the_payload():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload, _ = decode_sent(request)
        seen.update(payload)
        return httpx.Response(200, json={"status": "success"})

    client_with(handler).create_payment(amount=1, order_id="o")
    assert "description" not in seen
    assert "other_attr" not in seen


def test_gateway_error_is_raised_on_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "error", "code": "116", "message": "no funds"})

    with pytest.raises(GatewayError) as info:
        client_with(handler).get_status("te1")

    assert info.value.code == "116"
    assert "no funds" in str(info.value)


def test_failed_status_is_returned_not_raised():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "failed", "code": "116", "message": "Decline, insufficient funds"}
        )

    result = client_with(handler).get_status("te1")
    assert not result.ok
    assert result.status == "failed"
    assert result.get("code") == "116"


def test_transport_error_on_non_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>down</html>")

    with pytest.raises(TransportError):
        client_with(handler).get_status("te1")


def test_transport_error_on_http_500():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    with pytest.raises(TransportError) as info:
        client_with(handler).get_status("te1")

    assert info.value.status_code == 500


def test_language_default_is_applied_and_overridable():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload, _ = decode_sent(request)
        seen.clear()
        seen.update(payload)
        return httpx.Response(200, json={"status": "success"})

    client = client_with(handler)
    client.create_payment(amount=1, order_id="a")
    assert seen["language"] == "az"

    client.create_payment(amount=1, order_id="b", language="en")
    assert seen["language"] == "en"


def test_b2b_is_sent_as_json():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content_type"] = request.headers.get("content-type", "")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "success", "order_id": "b1"})

    client_with(handler).create_bank_transfer(
        order_id="b1",
        amount=100,
        description="fees",
        iban="AZ21NABZ00000000137010001944",
        name="ACME",
        tin="1234567892",
        bank_code="505141",
    )
    assert "application/json" in seen["content_type"]
    assert "data" in seen["body"]
    assert "signature" in seen["body"]


def test_enums_go_over_the_wire_as_plain_strings():
    from epoint import Currency, Language, OperationCode, Status

    assert json.dumps({"language": Language.AZ, "currency": Currency.AZN}) == (
        '{"language": "az", "currency": "AZN"}'
    )
    assert OperationCode.PAYMENT == "100"
    assert "success" in {Status.SUCCESS, Status.NEW}


def test_a_raw_status_string_still_reads_as_ok():
    from epoint.models import Response

    assert Response({"status": "success"}).ok
    assert not Response({"status": "failed"}).ok


def test_card_registration_sends_the_redirect_urls_it_is_given():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload, _ = decode_sent(request)
        seen.update(payload)
        return httpx.Response(200, json={"status": "success", "card_id": "ce1"})

    client_with(handler).register_card(
        success_redirect_url="https://shop.test/ok",
        error_redirect_url="https://shop.test/fail",
    )
    assert seen["success_redirect_url"] == "https://shop.test/ok"
    assert seen["error_redirect_url"] == "https://shop.test/fail"
    assert seen["refund"] == 0


def test_card_registration_falls_back_to_the_client_redirect_urls():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload, _ = decode_sent(request)
        seen.clear()
        seen.update(payload)
        return httpx.Response(200, json={"status": "success", "card_id": "ce1"})

    client = EpointClient(
        PUBLIC_KEY,
        PRIVATE_KEY,
        base_url="https://epoint.test",
        success_redirect_url="https://shop.test/default-ok",
        error_redirect_url="https://shop.test/default-fail",
        transport=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.register_card()
    assert seen["success_redirect_url"] == "https://shop.test/default-ok"
    assert seen["error_redirect_url"] == "https://shop.test/default-fail"

    client.register_card(success_redirect_url="https://shop.test/ok")
    assert seen["success_redirect_url"] == "https://shop.test/ok"
    assert seen["error_redirect_url"] == "https://shop.test/default-fail"

    client_with(handler).register_card()
    assert "success_redirect_url" not in seen
    assert "error_redirect_url" not in seen


def recording_client(seen: dict, response: Any = None) -> EpointClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.clear()
        seen["path"] = request.url.path
        if request.headers.get("content-type", "").startswith("application/json"):
            body = json.loads(request.content)
            seen["payload"] = json.loads(base64.b64decode(body["data"]))
        else:
            seen["payload"], _ = decode_sent(request)
        return httpx.Response(200, json={"status": "success"} if response is None else response)

    return EpointClient(
        PUBLIC_KEY,
        PRIVATE_KEY,
        base_url="https://epoint.test",
        success_redirect_url="https://shop.test/default-ok",
        error_redirect_url="https://shop.test/default-fail",
        transport=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_get_status_returns_a_payment_that_ended_in_error():
    body = {
        "status": "error",
        "code": "",
        "message": "An error occurred during payment",
        "transaction": "te1",
    }
    result = client_with(lambda request: httpx.Response(200, json=body)).get_status("te1")
    assert result.status == "error"
    assert result.message == "An error occurred during payment"
    assert result.code == ""
    assert not result.ok


def test_other_calls_still_raise_on_error_with_a_transaction():
    body = {"status": "error", "message": "bad", "transaction": "te1"}
    with pytest.raises(GatewayError):
        client_with(lambda request: httpx.Response(200, json=body)).create_payment(1, "o")


def test_token_split_payment_payload():
    seen: dict = {}
    client = recording_client(seen)
    client.create_token_split_payment(
        amount=100, order_id="o-1", split_account="i000000002", split_amount=30
    )
    assert seen["path"] == "/api/1/token/split-payment"
    payload = seen["payload"]
    assert payload["amount"] == "100.00"
    assert payload["split_user"] == "i000000002"
    assert payload["split_amount"] == "30.00"
    assert payload["currency"] == "AZN"
    assert payload["language"] == "az"
    assert payload["order_id"] == "o-1"
    assert payload["success_redirect_url"] == "https://shop.test/default-ok"
    assert payload["error_redirect_url"] == "https://shop.test/default-fail"

    client.create_token_split_payment(
        amount=10,
        order_id="o-2",
        split_account="i000000002",
        split_amount=3,
        description="share",
        success_redirect_url="https://shop.test/ok",
        other_attr={"k": "v"},
    )
    assert seen["payload"]["success_redirect_url"] == "https://shop.test/ok"
    assert seen["payload"]["error_redirect_url"] == "https://shop.test/default-fail"
    assert seen["payload"]["description"] == "share"
    assert seen["payload"]["other_attr"] == {"k": "v"}


def test_checkout_form_is_signed_and_makes_no_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("checkout_form must not send a request")

    client = EpointClient(
        PUBLIC_KEY,
        PRIVATE_KEY,
        base_url="https://epoint.test/",
        success_redirect_url="https://shop.test/default-ok",
        transport=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    form = client.checkout_form(
        amount=30.75, order_id="o-1", description="Kilim", is_installment=True
    )
    assert form.url == "https://epoint.test/api/1/checkout"
    assert matches(PRIVATE_KEY, form.data, form.signature)
    assert form.fields == {"data": form.data, "signature": form.signature}
    payload = json.loads(base64.b64decode(form.data))
    assert payload == {
        "public_key": PUBLIC_KEY,
        "amount": "30.75",
        "currency": "AZN",
        "language": "az",
        "order_id": "o-1",
        "description": "Kilim",
        "success_redirect_url": "https://shop.test/default-ok",
        "is_installment": 1,
    }


@pytest.mark.parametrize(("value", "sent"), [(True, 1), (False, 0), (None, None)])
def test_is_installment_is_sent_as_an_integer_or_omitted(value, sent):
    seen: dict = {}
    client = recording_client(seen)
    for call, path in (
        (client.create_payment, "/api/1/request"),
        (client.create_payment_request, "/api/1/payment-request"),
    ):
        call(amount=1, order_id="o", is_installment=value)
        assert seen["path"] == path
        assert seen["payload"].get("is_installment") == sent
        assert ("is_installment" in seen["payload"]) == (value is not None)

    form = client.checkout_form(amount=1, order_id="o", is_installment=value)
    payload = json.loads(base64.b64decode(form.data))
    assert payload.get("is_installment") == sent
    assert ("is_installment" in payload) == (value is not None)


def test_bank_transfer_sends_bulk_description():
    seen: dict = {}
    recording_client(seen).create_bank_transfer(
        order_id="b1",
        amount=100,
        description="fees",
        iban="AZ21NABZ00000000137010001944",
        name="ACME",
        tin="1234567892",
        bank_code="505141",
        bulk_description="July payroll",
    )
    assert seen["path"] == "/api/1/b2b/payment"
    assert seen["payload"]["bulk_description"] == "July payroll"


def test_installment_plans_send_description_and_other_attr():
    seen: dict = {}
    recording_client(seen, []).get_installment_plans(
        order_id="o", amount=200, description="sofa", other_attr={"k": "v"}
    )
    assert seen["path"] == "/api/1/get-installment-request"
    assert seen["payload"]["description"] == "sofa"
    assert seen["payload"]["other_attr"] == {"k": "v"}


def test_pay_by_installment_sends_other_attr():
    seen: dict = {}
    recording_client(seen).pay_by_installment(
        amount=200,
        order_id="o",
        installment_card_id="kapital",
        installment_month=6,
        other_attr={"k": "v"},
    )
    assert seen["path"] == "/api/1/installment-request"
    assert seen["payload"]["other_attr"] == {"k": "v"}
    assert seen["payload"]["installment_month"] == 6


def test_update_invoice_sends_tin_contract_and_merchant_order():
    seen: dict = {}
    client = recording_client(seen)
    client.update_invoice(
        7,
        amount=11,
        period_from="2026-01-01",
        period_to="2026-12-31",
        tin="1234567892",
        contract_number="C-1",
        merchant_order_id="M-1",
    )
    assert seen["path"] == "/api/1/invoices/update"
    payload = seen["payload"]
    assert payload["id"] == 7
    assert payload["inn"] == "1234567892"
    assert payload["contract_number"] == "C-1"
    assert payload["merchant_order_id"] == "M-1"

    client.update_invoice(7, amount=11, period_from="2026-01-01", period_to="2026-12-31")
    assert "inn" not in seen["payload"]
    assert "contract_number" not in seen["payload"]
    assert "merchant_order_id" not in seen["payload"]
