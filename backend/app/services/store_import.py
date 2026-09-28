"""Import a canonical receipt from any store adapter into the core."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import NormalizedReceipt, StoreAdapter
from app.adapters.lidl_client import LidlClientError, LidlNotConfigured
from app.models import Receipt, Store
from app.schemas.receipt import ReceiptCreate, ReceiptLineCreate, ReceiptRead
from app.services.receipts import import_receipt


def get_or_create_store(db: Session, name: str) -> Store:
    store = db.scalar(select(Store).where(Store.name == name))
    if store is None:
        store = Store(name=name)
        db.add(store)
        db.flush()
    return store


def to_receipt_create(store_id: int, receipt: NormalizedReceipt) -> ReceiptCreate:
    return ReceiptCreate(
        store_id=store_id,
        external_receipt_id=receipt.external_receipt_id,
        purchased_at=receipt.purchased_at,
        total_price=receipt.total_price,
        currency=receipt.currency,
        lines=[
            ReceiptLineCreate(
                external_product_id=line.external_product_id,
                name=line.name,
                package_count=line.package_count,
                unit_price=line.unit_price,
                line_total=line.line_total,
            )
            for line in receipt.lines
        ],
    )


def import_from_adapter(db: Session, adapter: StoreAdapter, raw: object) -> ReceiptRead:
    store = get_or_create_store(db, adapter.display_name)
    return import_receipt(db, to_receipt_create(store.id, adapter.normalize(raw)))


def existing_receipt_ids(db: Session, store_id: int) -> set[str]:
    return set(db.scalars(select(Receipt.external_receipt_id).where(Receipt.store_id == store_id)).all())


def sync_adapter(db: Session, adapter: StoreAdapter) -> dict:
    """Pull new receipts from a live source. Unknown SKUs stay in the review queue."""
    try:
        summaries = adapter.list_summaries()
    except LidlNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LidlClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    store = get_or_create_store(db, adapter.display_name)
    known = existing_receipt_ids(db, store.id)
    imported = 0
    skipped = 0
    errors: list[str] = []

    for summary in summaries:
        if summary.external_receipt_id in known:
            skipped += 1
            continue
        try:
            raw = adapter.fetch_raw(summary.external_receipt_id)
            import_from_adapter(db, adapter, raw)
            known.add(summary.external_receipt_id)
            imported += 1
        except HTTPException as exc:
            if exc.status_code == 409:
                skipped += 1
                continue
            errors.append(f"{summary.external_receipt_id}: {exc.detail}")
        except (ValueError, NotImplementedError, LidlClientError) as exc:
            errors.append(f"{summary.external_receipt_id}: {exc}")

    return {
        "adapter": adapter.key,
        "store_id": store.id,
        "imported": imported,
        "skipped": skipped,
        "failed": len(errors),
        "errors": errors,
    }
