# Changelog

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
