"""Current inventory derived from purchases minus consumptions."""

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Consumption, Product, Purchase
from app.schemas.inventory import InventoryItem

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryItem])
def list_inventory(db: Session = Depends(get_db)) -> list[InventoryItem]:
    purchased = (
        select(Purchase.product_id, func.coalesce(func.sum(Purchase.quantity), 0).label("qty"))
        .group_by(Purchase.product_id)
        .subquery()
    )
    consumed = (
        select(Consumption.product_id, func.coalesce(func.sum(Consumption.quantity), 0).label("qty"))
        .group_by(Consumption.product_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Product.id,
            Product.name,
            Product.base_unit,
            Product.minimum_stock,
            (func.coalesce(purchased.c.qty, 0) - func.coalesce(consumed.c.qty, 0)).label("quantity"),
        )
        .outerjoin(purchased, purchased.c.product_id == Product.id)
        .outerjoin(consumed, consumed.c.product_id == Product.id)
        .order_by(Product.name)
    ).all()

    return [
        InventoryItem(
            product_id=row.id,
            name=row.name,
            unit=row.base_unit,
            quantity=Decimal(row.quantity),
            minimum_stock=row.minimum_stock,
        )
        for row in rows
    ]
