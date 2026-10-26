"""Consumption HTTP routes. A consumption is a stock-out transaction."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Consumption, Product, Purchase
from app.schemas.consumption import ConsumptionCreate, ConsumptionRead, ConsumptionZero

router = APIRouter(prefix="/consumptions", tags=["consumptions"])


def _on_hand(db: Session, product_id: int) -> Decimal:
    purchased = db.scalar(
        select(func.coalesce(func.sum(Purchase.quantity), 0)).where(Purchase.product_id == product_id)
    )
    consumed = db.scalar(
        select(func.coalesce(func.sum(Consumption.quantity), 0)).where(Consumption.product_id == product_id)
    )
    return Decimal(purchased or 0) - Decimal(consumed or 0)


def _to_read(consumption: Consumption, product_name: str) -> ConsumptionRead:
    return ConsumptionRead(
        id=consumption.id,
        product_id=consumption.product_id,
        product_name=product_name,
        quantity=consumption.quantity,
        unit=consumption.unit,
        consumed_at=consumption.consumed_at,
        source=consumption.source,
    )


def _write_off(db: Session, product: Product, quantity: Decimal) -> Consumption:
    available = _on_hand(db, product.id)
    if available <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="На складе уже нечего списывать",
        )
    if quantity > available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Нельзя списать больше, чем есть на складе",
        )

    consumption = Consumption(
        product_id=product.id,
        quantity=quantity,
        unit=product.base_unit,
        consumed_at=datetime.now(timezone.utc),
        source="manual",
        reference_id=str(uuid4()),
    )
    db.add(consumption)
    db.commit()
    db.refresh(consumption)
    return consumption


@router.post("", response_model=ConsumptionRead, status_code=status.HTTP_201_CREATED)
def create_consumption(payload: ConsumptionCreate, db: Session = Depends(get_db)) -> ConsumptionRead:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Продукт не найден")
    if payload.unit != product.base_unit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Единица должна совпадать с единицей продукта '{product.base_unit}'",
        )
    consumption = _write_off(db, product, payload.quantity)
    return _to_read(consumption, product.name)


@router.post("/zero", response_model=ConsumptionRead, status_code=status.HTTP_201_CREATED)
def zero_consumption(payload: ConsumptionZero, db: Session = Depends(get_db)) -> ConsumptionRead:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Продукт не найден")
    available = _on_hand(db, product.id)
    consumption = _write_off(db, product, available)
    return _to_read(consumption, product.name)
