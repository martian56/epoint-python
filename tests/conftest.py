import os

import httpx
import pytest

from epoint import EpointClient

SANDBOX_URL = os.environ.get("EPOINT_BASE_URL", "http://localhost:8181")
PUBLIC_KEY = "i000000001"
PRIVATE_KEY = "sandbox_private_key_0000000001"


def _sandbox_up() -> bool:
    try:
        return httpx.get(f"{SANDBOX_URL}/api/heartbeat", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session")
def sandbox_available() -> bool:
    return _sandbox_up()


@pytest.fixture
def client(sandbox_available: bool):
    if not sandbox_available:
        pytest.skip(f"no sandbox on {SANDBOX_URL}")
    with EpointClient(PUBLIC_KEY, PRIVATE_KEY, base_url=SANDBOX_URL, language="en") as c:
        yield c


@pytest.fixture
def pay():
    def _pay(client: EpointClient, redirect_url: str, card: str = "4111111111111111") -> None:
        token = redirect_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
        httpx.post(
            f"{SANDBOX_URL}/checkout/{token}",
            data={"card_number": card, "card_holder": "TESTER", "month": "12", "year": "30"},
        )

    return _pay
