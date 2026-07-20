import base64
import json

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
