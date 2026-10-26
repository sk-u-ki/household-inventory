"""Pydantic schemas for stock-out."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import BaseUnit


class ConsumptionCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    unit: BaseUnit


class ConsumptionZero(BaseModel):
    product_id: int


class ConsumptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    quantity: Decimal
    unit: BaseUnit
    consumed_at: datetime
    source: str
