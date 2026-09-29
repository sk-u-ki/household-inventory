"""Pydantic schemas for internal products."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


BaseUnit = Literal["g", "ml", "pcs"]


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_unit: BaseUnit
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("name must not be empty")
        return name


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    base_unit: BaseUnit | None = None
    minimum_stock: Decimal | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        if not name:
            raise ValueError("name must not be empty")
        return name


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_unit: BaseUnit
    minimum_stock: Decimal
    created_at: datetime
    updated_at: datetime
