"""Store-agnostic receipt adapter contract.

A new shop is one class: map that shop's payload into NormalizedReceipt.
Import, mappings and inventory stay in the core and do not know Lidl.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ReceiptSummary(BaseModel):
    """Cheap list item used to skip receipts already in the database."""

    external_receipt_id: str
    purchased_at: datetime | None = None
    total_price: Decimal | None = None


class NormalizedLine(BaseModel):
    external_product_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    package_count: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    line_total: Decimal = Field(ge=0)


class NormalizedReceipt(BaseModel):
    """Canonical receipt. Core import only accepts this shape."""

    external_receipt_id: str = Field(min_length=1)
    purchased_at: datetime
    total_price: Decimal = Field(ge=0)
    currency: str = Field(default="PLN", min_length=3, max_length=3)
    lines: list[NormalizedLine] = Field(min_length=1)


class StoreAdapter(ABC):
    """One store chain. `key` is stable (`lidl`), `display_name` is the Store row."""

    key: str
    display_name: str

    @abstractmethod
    def normalize(self, raw: Any) -> NormalizedReceipt:
        """Turn a store-specific payload into a canonical receipt. No I/O."""

    def list_summaries(self) -> list[ReceiptSummary]:
        raise NotImplementedError(f"{self.key} has no live receipt source yet")

    def fetch_raw(self, external_receipt_id: str) -> Any:
        raise NotImplementedError(f"{self.key} has no live receipt source yet")
