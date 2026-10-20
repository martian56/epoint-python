import json

import pytest

from epoint import (
    OK_STATUSES,
    B2BWebhook,
    B2BWebhookStatus,
    Callback,
    EpointError,
    GatewayError,
    TransportError,
    parse_b2b_webhook,
)
from epoint._transport import parse
from epoint.models import Response


def test_get_status_returns_a_payment_that_ended_in_error():
    body = {"status": "error", "code": "", "message": "An error occurred", "transaction": "te1"}
    result = parse(200, body, payment_status=True)
    assert result.status == "error"
    assert result.transaction == "te1"
    assert not result.ok


def test_get_status_still_raises_for_an_error_with_no_transaction():
    with pytest.raises(GatewayError) as info:
        parse(200, {"status": "error", "message": "Unknown transaction"}, payment_status=True)
    assert "Unknown transaction" in str(info.value)


def test_get_status_still_raises_for_an_error_with_a_non_2xx_status():
    body = {"status": "error", "message": "denied", "transaction": "te1"}
    with pytest.raises(GatewayError):
        parse(403, body, payment_status=True)


def test_get_status_still_raises_transport_error_on_http_500():
    with pytest.raises(TransportError):
        parse(500, {"detail": "boom", "transaction": "te1"}, payment_status=True)


def test_other_endpoints_still_raise_on_error_with_a_transaction():
    with pytest.raises(GatewayError):
        parse(200, {"status": "error", "message": "bad", "transaction": "te1"})


@pytest.mark.parametrize("status", ["success", "SUCCESS", "ok"])
def test_ok_is_true_for_the_success_statuses(status):
    assert Response({"status": status}).ok
    assert status in OK_STATUSES


@pytest.mark.parametrize(
    "status",
    ["error", "failed", "server_error", "returned", "new", "FAILED", "PENDING", "OK", None],
)
def test_ok_is_false_for_everything_else(status):
    assert not Response({"status": status}).ok


def test_callback_ok_stays_lower_case_success_only():
    base = {"order_id": "o", "transaction": "te1"}
    assert Callback.from_dict({**base, "status": "success"}).ok
    assert not Callback.from_dict({**base, "status": "SUCCESS"}).ok
    assert not Callback.from_dict({**base, "status": "ok"}).ok


def test_typed_accessors_read_the_documented_fields():
    r = Response(
        {
            "status": "success",
            "trace_id": "tr1",
            "code": "000",
            "bank_transaction": "BT1",
            "bank_response": "000",
            "operation_code": "100",
            "rrn": 123456789012,
            "card_name": "TESTER",
            "card_mask": "411111******1111",
            "amount": 25.5,
            "card_id": "ce1",
            "order_id": "o-1",
            "widget_url": "https://epoint.test/widget",
        }
    )
    assert r.trace_id == "tr1"
    assert r.code == "000"
    assert r.bank_transaction == "BT1"
    assert r.bank_response == "000"
    assert r.operation_code == "100"
    assert r.rrn == "123456789012"
    assert r.card_name == "TESTER"
    assert r.card_mask == "411111******1111"
    assert r.amount == 25.5
    assert r.card_id == "ce1"
    assert r.order_id == "o-1"
    assert r.widget_url == "https://epoint.test/widget"
    assert r.raw["rrn"] == 123456789012
    assert r.get("rrn") == 123456789012


def test_typed_accessors_are_none_when_missing():
    r = Response({"status": "success"})
    for name in (
        "trace_id",
        "code",
        "bank_transaction",
        "bank_response",
        "operation_code",
        "rrn",
        "card_name",
        "card_mask",
        "amount",
        "card_id",
        "order_id",
        "widget_url",
    ):
        assert getattr(r, name) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(10, 10.0), (30.75, 30.75), ("30.75", 30.75), (" 5 ", 5.0), ("abc", None), (True, None)],
)
def test_amount_accepts_a_number_or_a_numeric_string(value, expected):
    assert Response({"amount": value}).amount == expected


def test_callback_carries_the_new_optional_fields():
    callback = Callback.from_dict(
        {
            "order_id": "o",
            "status": "success",
            "transaction": "te1",
            "bank_response": "000",
            "trace_id": "tr1",
            "card_id": "ce1",
            "amount": "12.50",
        }
    )
    assert callback.bank_response == "000"
    assert callback.trace_id == "tr1"
    assert callback.card_id == "ce1"
    assert callback.amount == 12.5


def test_callback_new_fields_default_to_none():
    callback = Callback.from_dict({"order_id": "o", "status": "success"})
    assert callback.bank_response is None
    assert callback.trace_id is None
    assert callback.card_id is None


WEBHOOK = {
    "order_id": "b2b-1",
    "status": "success",
    "amount": 1250.0,
    "payee_iban": "AZ21NABZ00000000137010001944",
    "payee_name": "Logistika MMC",
    "error_message": None,
}


def test_b2b_webhook_is_parsed_from_a_json_string():
    hook = parse_b2b_webhook(json.dumps(WEBHOOK))
    assert isinstance(hook, B2BWebhook)
    assert hook.order_id == "b2b-1"
    assert hook.status == B2BWebhookStatus.SUCCESS
    assert hook.ok
    assert hook.amount == 1250.0
    assert hook.payee_iban == "AZ21NABZ00000000137010001944"
    assert hook.payee_name == "Logistika MMC"
    assert hook.error_message is None


def test_b2b_webhook_accepts_bytes_and_a_dict():
    assert parse_b2b_webhook(json.dumps(WEBHOOK).encode()).order_id == "b2b-1"
    assert parse_b2b_webhook(WEBHOOK).order_id == "b2b-1"


def test_b2b_webhook_failure_carries_the_error_message():
    hook = parse_b2b_webhook(
        {**WEBHOOK, "status": "failed", "amount": "1250.00", "error_message": "IBAN closed"}
    )
    assert hook.status == B2BWebhookStatus.FAILED
    assert not hook.ok
    assert hook.amount == 1250.0
    assert hook.error_message == "IBAN closed"


def test_b2b_webhook_ignores_unknown_fields_and_keeps_an_unknown_status():
    hook = parse_b2b_webhook({**WEBHOOK, "status": "reversed", "extra": 1})
    assert hook.status == "reversed"
    assert not hook.ok
    assert hook.raw["extra"] == 1


def test_b2b_webhook_rejects_a_body_that_is_not_a_json_object():
    with pytest.raises(EpointError):
        parse_b2b_webhook("not json")
    with pytest.raises(EpointError):
        parse_b2b_webhook("[1, 2]")
