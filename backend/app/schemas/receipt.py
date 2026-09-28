"""Pydantic schemas for receipts and reviewable receipt lines."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import BaseUnit, ProductCreate


class ReceiptLineCreate(BaseModel):
    external_product_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    package_count: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    line_total: Decimal = Field(ge=0)


class ReceiptCreate(BaseModel):
    store_id: int
    external_receipt_id: str = Field(min_length=1)
    purchased_at: datetime
    total_price: Decimal = Field(ge=0)
    currency: str = Field(default="PLN", min_length=3, max_length=3)
    lines: list[ReceiptLineCreate] = Field(min_length=1)


class ReceiptLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_id: int
    store_id: int
    store_name: str
    external_product_id: str
    name: str
    package_count: Decimal
    unit_price: Decimal
    line_total: Decimal
    status: Literal["unmapped", "mapped"]
    purchase_id: int | None
    occurrence_count: int = 1
    total_package_count: Decimal | None = None
    created_at: datetime


class ReceiptRead(BaseModel):
    id: int
    store_id: int
    external_receipt_id: str
    purchased_at: datetime
    total_price: Decimal
    currency: str
    mapped_count: int
    unmapped_count: int
    lines: list[ReceiptLineRead]


class ReceiptLineMapExisting(BaseModel):
    """Bind a store SKU to a Product that already exists."""

    product_id: int
    package_quantity: Decimal | None = Field(default=None, gt=0)
    package_unit: BaseUnit | None = None


class ReceiptLineCreateAndMap(BaseModel):
    """Create an internal Product, then bind this store SKU to it."""

    product: ProductCreate
    package_quantity: Decimal = Field(gt=0)
    package_unit: BaseUnit
