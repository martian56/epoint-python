import base64
import hashlib

import pytest

from epoint import SignatureError, verify_callback
from epoint._signing import decode_data, encode_payload, matches, sign

PRIVATE_KEY = "d3hjsl38sd8kdfhbcea0be04eafde9e8e2bad2fb092d"


def test_sign_matches_the_documented_formula():
    data = encode_payload({"public_key": "i000000001", "amount": "30.75"})
    expected = base64.b64encode(
        hashlib.sha1(f"{PRIVATE_KEY}{data}{PRIVATE_KEY}".encode()).digest()
    ).decode()
    assert sign(PRIVATE_KEY, data) == expected


def test_sign_uses_the_raw_digest_not_hex():
    data = encode_payload({"amount": "1.00"})
    hex_signature = base64.b64encode(
        hashlib.sha1(f"{PRIVATE_KEY}{data}{PRIVATE_KEY}".encode()).hexdigest().encode()
    ).decode()
    assert sign(PRIVATE_KEY, data) != hex_signature


def test_matches_is_true_for_a_correct_pair():
    data = encode_payload({"amount": "5.00"})
    assert matches(PRIVATE_KEY, data, sign(PRIVATE_KEY, data))


def test_matches_is_false_for_a_wrong_signature():
    data = encode_payload({"amount": "5.00"})
    assert not matches(PRIVATE_KEY, data, "wrong")


def test_decode_data_round_trips():
    payload = {"order_id": "x", "status": "success"}
    assert decode_data(encode_payload(payload)) == payload


def test_decode_data_rejects_garbage():
    with pytest.raises(SignatureError):
        decode_data("not base64 json")


def test_verify_callback_returns_the_decoded_payload():
    payload = {
        "order_id": "order-1",
        "status": "success",
        "code": "000",
        "transaction": "te0000000001",
        "amount": 30.75,
    }
    data = encode_payload(payload)
    callback = verify_callback(PRIVATE_KEY, data, sign(PRIVATE_KEY, data))

    assert callback.ok
    assert callback.order_id == "order-1"
    assert callback.transaction == "te0000000001"
    assert callback.amount == 30.75


def test_verify_callback_rejects_a_tampered_payload():
    data = encode_payload({"order_id": "order-1", "amount": 1})
    good = sign(PRIVATE_KEY, data)
    tampered = encode_payload({"order_id": "order-1", "amount": 9999})

    with pytest.raises(SignatureError):
        verify_callback(PRIVATE_KEY, tampered, good)
