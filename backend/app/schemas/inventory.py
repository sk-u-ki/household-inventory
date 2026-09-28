"""Pydantic schemas for derived inventory."""

from decimal import Decimal

from pydantic import BaseModel

from app.schemas.product import BaseUnit


class InventoryItem(BaseModel):
    product_id: int
    name: str
    unit: BaseUnit
    quantity: Decimal
    minimum_stock: Decimal
