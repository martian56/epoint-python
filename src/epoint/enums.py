from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """A str subclass, so members go over the wire unchanged.

    Python 3.11 has this built in. Defining it here keeps 3.10 working.
    """

    __hash__ = str.__hash__

    def __str__(self) -> str:
        return str(self.value)


class Status(StrEnum):
    """The status on a response or a callback."""

    NEW = "new"
    SUCCESS = "success"
    FAILED = "failed"
    ERROR = "error"
    RETURNED = "returned"
    SERVER_ERROR = "server_error"


SETTLED_STATUSES = frozenset({Status.SUCCESS.value})


class CardStatus(StrEnum):
    NEW = "new"
    ACTIVE = "active"
    PENDING = "pending"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SESSION_EXPIRED = "session_expired"


USABLE_CARD_STATUSES = frozenset({CardStatus.ACTIVE.value})


class InvoiceStatus(StrEnum):
    WAITING = "waiting_for_payment"
    PAID = "paid"
    CANCELED = "canceled"


class B2BStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class B2BWebhookStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


HEARTBEAT_OK = "ok"

OK_STATUSES = frozenset({Status.SUCCESS.value, B2BStatus.SUCCESS.value, HEARTBEAT_OK})


class OperationCode(StrEnum):
    """What the transaction did, as it comes back on a callback."""

    CARD_REGISTRATION = "001"
    PAYMENT = "100"
    REGISTRATION_WITH_PAYMENT = "200"


class Language(StrEnum):
    AZ = "az"
    EN = "en"
    RU = "ru"


class Currency(StrEnum):
    AZN = "AZN"
    USD = "USD"
    EUR = "EUR"
    RUB = "RUB"


#: Checkout takes any of these.
SUPPORTED_CURRENCIES = frozenset(c.value for c in Currency)

#: Split, pre-auth, refund, reverse, payout and wallet take AZN and nothing else.
AZN_ONLY = frozenset({Currency.AZN.value})
