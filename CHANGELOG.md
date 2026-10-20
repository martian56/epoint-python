# Changelog

## 0.4.0

Every change applies to `EpointClient` and `AsyncEpointClient`.

- `get_status` returns a payment that ended in status `error` instead of raising. On
  `get_status`, a 2xx response with `status: "error"` and a `transaction` field is a payment
  state. Any other error body and any 4xx or 5xx answer still raise `GatewayError`, and other
  methods behave as before.
- `Response.ok` is also true for the B2B `SUCCESS` and the heartbeat's `ok`, listed in the new
  `OK_STATUSES`.
- `create_token_split_payment` posts to `/api/1/token/split-payment`, the split payment for
  Apple Pay and Google Pay, with the same arguments as `create_split_payment`.
- `checkout_form` builds the signed fields and action URL for the browser form post to
  `/api/1/checkout`, returned as a `CheckoutForm`, without making a request.
- New optional parameters: `is_installment` on `create_payment`, `checkout_form` and
  `create_payment_request`; `bulk_description` on `create_bank_transfer`; `description` and
  `other_attr` on `get_installment_plans`; `other_attr` on `pay_by_installment`; `tin`,
  `contract_number` and `merchant_order_id` on `update_invoice`.
- `Response` has typed attributes for `trace_id`, `code`, `bank_transaction`, `bank_response`,
  `operation_code`, `rrn`, `card_name`, `card_mask`, `amount`, `card_id`, `order_id` and
  `widget_url`. `amount` is a float read from a number or a numeric string.
- `Callback` carries the optional `bank_response`, `trace_id` and `card_id`.
- `parse_b2b_webhook` turns a B2B webhook body into a typed `B2BWebhook`. The docs define no
  signature for it, so confirm the result with `get_bank_transfer` before acting on it.

## 0.3.0

- `register_card` takes `success_redirect_url` and `error_redirect_url`, so a card saved without
  a payment returns the customer to your own page. Without them it uses the client's defaults, as
  the pay methods do. This applies to `EpointClient` and `AsyncEpointClient`.

## 0.2.1

- The README documents the enums and uses them in its examples, instead of the bare strings it
  still showed.

## 0.2.0

- Enums for the values the API uses: `Status`, `CardStatus`, `InvoiceStatus`, `B2BStatus`,
  `OperationCode`, `Language` and `Currency`. Values come from the sandbox's own definitions, so
  they match what the API sends. `Currency` also records that checkout takes AZN, USD, EUR and
  RUB while split, pre-auth, refund, reverse, payout and wallet take AZN only.
- Raw strings still work everywhere they did before.

## 0.1.1

Documentation and packaging only, no library changes since 0.1.0. First release
published through the automated trusted-publishing workflow.

- Add this changelog.

## 0.1.0

First release.

- `EpointClient` and `AsyncEpointClient`, covering all 30 documented endpoints:
  payments, saved cards, refunds and payouts, split payments, pre-authorisation,
  installments, wallets, Apple Pay and Google Pay, invoices, and B2B transfers.
- Request signing and callback verification.
- Typed throughout, `httpx` as the only dependency.
- Integration tests run against the [epoint-sandbox](https://github.com/martian56/epoint-sandbox).
