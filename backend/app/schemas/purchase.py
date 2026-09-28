"""Pydantic schemas for purchases."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import BaseUnit


class PurchaseCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    unit: BaseUnit
    store_id: int | None = None
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    total_price: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="PLN", min_length=3, max_length=3)


class PurchaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_id: int
    product_id: int
    product_name: str
    quantity: Decimal
    unit: BaseUnit
    unit_price: Decimal
    total_price: Decimal
    created_at: datetime
