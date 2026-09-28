"""Receipt import and user review of unknown store products."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.receipt import (
    ReceiptCreate,
    ReceiptLineCreateAndMap,
    ReceiptLineMapExisting,
    ReceiptLineRead,
    ReceiptRead,
)
from app.services.receipts import create_product_and_map, import_receipt, list_receipt_lines, map_existing_product

receipts_router = APIRouter(prefix="/receipts", tags=["receipts"])
receipt_lines_router = APIRouter(prefix="/receipt-lines", tags=["receipt-lines"])


@receipts_router.post("", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
def create_receipt(payload: ReceiptCreate, db: Session = Depends(get_db)) -> ReceiptRead:
    return import_receipt(db, payload)


@receipt_lines_router.get("", response_model=list[ReceiptLineRead])
def get_receipt_lines(
    status_filter: str = Query(default="unmapped", alias="status", pattern="^(unmapped|mapped)$"),
    db: Session = Depends(get_db),
) -> list[ReceiptLineRead]:
    return list_receipt_lines(db, status_filter)


@receipt_lines_router.post("/{line_id}/resolve", response_model=ReceiptLineRead)
def resolve_existing_product(
    line_id: int,
    payload: ReceiptLineMapExisting,
    db: Session = Depends(get_db),
) -> ReceiptLineRead:
    return map_existing_product(
        db,
        line_id,
        payload.product_id,
        payload.package_quantity,
        payload.package_unit,
    )


@receipt_lines_router.post("/{line_id}/create-and-resolve", response_model=ReceiptLineRead, status_code=status.HTTP_201_CREATED)
def resolve_new_product(
    line_id: int,
    payload: ReceiptLineCreateAndMap,
    db: Session = Depends(get_db),
) -> ReceiptLineRead:
    return create_product_and_map(
        db,
        line_id,
        payload.product,
        payload.package_quantity,
        payload.package_unit,
    )
