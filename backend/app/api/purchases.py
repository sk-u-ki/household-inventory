"""Purchase HTTP routes. A purchase is a stock-in transaction."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, Purchase, Receipt, Store
from app.schemas.purchase import PurchaseCreate, PurchaseRead

router = APIRouter(prefix="/purchases", tags=["purchases"])

MANUAL_STORE_NAME = "Manual"


def _resolve_store(db: Session, store_id: int | None) -> Store:
    if store_id is not None:
        store = db.get(Store, store_id)
        if store is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
        return store

    store = db.scalar(select(Store).where(Store.name == MANUAL_STORE_NAME))
    if store is None:
        store = Store(name=MANUAL_STORE_NAME)
        db.add(store)
        db.flush()
    return store


def _to_read(purchase: Purchase, product_name: str) -> PurchaseRead:
    return PurchaseRead(
        id=purchase.id,
        receipt_id=purchase.receipt_id,
        product_id=purchase.product_id,
        product_name=product_name,
        quantity=purchase.quantity,
        unit=purchase.unit,
        unit_price=purchase.unit_price,
        total_price=purchase.total_price,
        created_at=purchase.created_at,
    )


@router.get("", response_model=list[PurchaseRead])
def list_purchases(db: Session = Depends(get_db)) -> list[PurchaseRead]:
    rows = db.execute(
        select(Purchase, Product.name)
        .join(Product, Product.id == Purchase.product_id)
        .order_by(Purchase.id.desc())
    ).all()
    return [_to_read(purchase, name) for purchase, name in rows]


@router.post("", response_model=PurchaseRead, status_code=status.HTTP_201_CREATED)
def create_purchase(payload: PurchaseCreate, db: Session = Depends(get_db)) -> PurchaseRead:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if payload.unit != product.base_unit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unit must match product base_unit '{product.base_unit}'",
        )

    store = _resolve_store(db, payload.store_id)
    receipt = Receipt(
        store_id=store.id,
        external_receipt_id=f"manual-{uuid4()}",
        purchased_at=datetime.now(timezone.utc),
        total_price=payload.total_price,
        currency=payload.currency.upper(),
    )
    db.add(receipt)
    db.flush()

    purchase = Purchase(
        receipt_id=receipt.id,
        product_id=product.id,
        quantity=payload.quantity,
        unit=payload.unit,
        unit_price=payload.unit_price,
        total_price=payload.total_price,
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    return _to_read(purchase, product.name)
