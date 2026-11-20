from enum import StrEnum


class LicenseStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class StockState(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIALLY_ALLOCATED = "PARTIALLY_ALLOCATED"
    FULLY_ALLOCATED = "FULLY_ALLOCATED"
    EXPIRED = "EXPIRED"
    DISABLED = "DISABLED"

    @property
    def label(self) -> str:
        return {
            "AVAILABLE": "Available",
            "PARTIALLY_ALLOCATED": "Partially allocated",
            "FULLY_ALLOCATED": "Fully allocated",
            "EXPIRED": "Expired",
            "DISABLED": "Disabled",
        }[self.value]


class AllocationStatus(StrEnum):
    ALLOCATED = "ALLOCATED"
    CONFIRMED = "CONFIRMED"
    RELEASED = "RELEASED"
    CONSUMED = "CONSUMED"


class SaleStatus(StrEnum):
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentMethod(StrEnum):
    CASH = "CASH"
    MOBILE_MONEY = "MOBILE_MONEY"
    BANK_TRANSFER = "BANK_TRANSFER"
    CARD = "CARD"
    OTHER = "OTHER"

    @property
    def label(self) -> str:
        return {
            "CASH": "Cash",
            "MOBILE_MONEY": "Mobile money",
            "BANK_TRANSFER": "Bank transfer",
            "CARD": "Card",
            "OTHER": "Other",
        }[self.value]


class DeliveryNoteStatus(StrEnum):
    ISSUED = "ISSUED"
    VOID = "VOID"


class EntryKind(StrEnum):
    OPENING_DEBT = "OPENING_DEBT"
    PAYMENT = "PAYMENT"


class PaymentState(StrEnum):
    PAID = "PAID"
    PARTLY_PAID = "PARTLY_PAID"
    UNPAID = "UNPAID"

    @property
    def label(self) -> str:
        return {"PAID": "Paid", "PARTLY_PAID": "Partly paid", "UNPAID": "Not paid"}[self.value]
