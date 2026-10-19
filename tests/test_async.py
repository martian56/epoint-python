import base64
import json
import os
import uuid

import httpx
import pytest

from epoint import AsyncEpointClient, GatewayError

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
