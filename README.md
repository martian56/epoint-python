# epoint

Python client for the [epoint.az](https://epoint.az) payment gateway.

Covers all 30 documented endpoints: payments, saved cards, refunds and payouts, split payments,
pre-authorisation, installments, wallets, Apple Pay and Google Pay, invoices, and B2B transfers.
Sync and async, fully typed, one dependency.

```bash
pip install epoint
```

## Quick start

```python
from epoint import EpointClient

client = EpointClient(public_key="i000000001", private_key="your-private-key")

payment = client.create_payment(amount=30.75, order_id="order-1", description="Test order")
print(payment.redirect_url)
```

Send the customer to `payment.redirect_url`. When they finish, epoint calls your result URL. Verify
it before trusting it:

```python
from epoint import SignatureError

try:
    callback = client.verify_callback(data, signature)
except SignatureError:
    return "invalid", 400

if callback.ok:
    fulfil(callback.order_id, callback.transaction)
```

## Async

`AsyncEpointClient` has the same methods, awaited:

```python
from epoint import AsyncEpointClient

async with AsyncEpointClient(public_key="i000000001", private_key="your-private-key") as client:
    payment = await client.create_payment(amount=30.75, order_id="order-1")
    status = await client.get_status(payment.transaction)
```

`verify_callback` stays synchronous on both clients, since it only does a signature check.

## Configuration

Pass keys directly, or read them from the environment:

```python
client = EpointClient.from_env()
```

| Variable | |
|---|---|
| `EPOINT_PUBLIC_KEY` | Required |
| `EPOINT_PRIVATE_KEY` | Required |
| `EPOINT_BASE_URL` | Defaults to `https://epoint.az` |
| `EPOINT_LANGUAGE` | Defaults to `az` |
| `EPOINT_SUCCESS_REDIRECT_URL` | Optional default for payment methods |
| `EPOINT_FAILED_REDIRECT_URL` | Optional default for payment methods |

`language` and `currency` are set once on the client and can be overridden per call.

## Testing against the sandbox

There is a local sandbox that behaves like the real gateway, so you can build and test without a
merchant account or real money:

```python
client = EpointClient(
    public_key="i000000001",
    private_key="sandbox_private_key_0000000001",
    base_url="http://localhost:8181",
)
```

See [epoint-sandbox](https://github.com/martian56/epoint-sandbox). Switching to production means
changing `base_url` and the keys, nothing else.

## Responses

Most methods return a `Response`. Read known fields as attributes, anything else through `get` or
`raw`:

```python
r = client.get_status("te0000000001")
r.status         # "success", compares equal to Status.SUCCESS
r.ok             # True
r.get("rrn")     # bank reference number
r.raw            # the full response dict
```

`create_payment`, `reserve`, `create_split_payment` and the other checkout methods return
`redirect_url`. `get_installment_plans` returns a list and `list_wallets` returns a dict.

## Enums

Every value the API uses has an enum. They come from the sandbox's own definitions, so they match
what production sends. Members are `str` subclasses, so they go over the wire unchanged and
compare equal to the raw value; a plain string still works anywhere an enum is accepted.

```python
from epoint import CardStatus, Currency, EpointClient, Language, Status

client = EpointClient.from_env(language=Language.EN, currency=Currency.USD)

status = client.get_status(transaction)
if status.status == Status.SUCCESS:
    fulfil(order_id)
```

| Enum | Values |
|---|---|
| `Status` | new, success, failed, error, returned, server_error |
| `CardStatus` | new, active, pending, rejected, expired, session_expired |
| `InvoiceStatus` | waiting_for_payment, paid, canceled |
| `B2BStatus` | PENDING, PROCESSING, SUCCESS, FAILED |
| `OperationCode` | 001 card registration, 100 payment, 200 registration with payment |
| `Language` | az, en, ru |
| `Currency` | AZN, USD, EUR, RUB |

Currency is not uniform across the API. Checkout takes all four, but split, pre-auth, refund,
reverse, payout and wallet take AZN and nothing else. `SUPPORTED_CURRENCIES` and `AZN_ONLY` hold
those two sets.

`SETTLED_STATUSES` is what `ok` checks, and `USABLE_CARD_STATUSES` is the set a card has to be in
before you can charge it.

## Saving a card without a payment

`register_card` saves a card with no charge, for example when the first period is free and later
ones are charged with `charge_saved_card`. Keep the `card_id` it returns and send the customer to
its `redirect_url`.

```python
registration = client.register_card(
    description="Card for renewals",
    success_redirect_url="https://shop.example/card/saved",
    error_redirect_url="https://shop.example/card/failed",
)
store_card(registration["card_id"])
```

The customer comes back to `success_redirect_url` or `error_redirect_url`, or to the client's own
defaults when neither is given. A card can be charged once `get_card_status` reports it `active`.

## Methods

| Group | Methods |
|---|---|
| Checkout | `create_payment`, `create_payment_request`, `create_amex_payment`, `change_payment_sum` |
| Status | `get_status`, `get_card_status`, `get_bank_transfer` |
| Split | `create_split_payment`, `split_charge_saved_card` |
| Pre-auth | `reserve`, `capture` |
| Saved cards | `register_card`, `register_card_and_pay`, `charge_saved_card` |
| Money back | `refund`, `reverse` |
| Installments | `get_installment_plans`, `pay_by_installment` |
| Wallets | `list_wallets`, `pay_with_wallet` |
| Apple Pay, Google Pay | `create_widget` |
| Invoices | `create_invoice`, `update_invoice`, `get_invoice`, `list_invoices`, `send_invoice_sms`, `send_invoice_email` |
| B2B | `create_bank_transfer`, `get_bank_transfer` |
| Health | `heartbeat` |

## Errors

| Exception | Raised when |
|---|---|
| `GatewayError` | epoint returned `status: error` or `failed`. Carries `code`, `message`, `payload`. |
| `TransportError` | Network failure, or a non-JSON or `4xx`/`5xx` response |
| `SignatureError` | A callback's signature did not match, or its data would not decode |

All three inherit from `EpointError`.

## Signatures

Epoint signs with `base64(sha1_raw(private_key + data + private_key))`. The client builds and
verifies these for you. The digest is the raw 20 bytes, not the hex string, which is where most
hand-rolled integrations go wrong.

## Not affiliated with Epoint

An independent client for developers integrating with epoint.az.

MIT licensed.
