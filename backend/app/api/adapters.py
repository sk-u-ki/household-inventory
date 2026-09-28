"""Store adapters: list shops and import a raw receipt from one of them."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters import get_adapter, list_adapters
from app.db import get_db
from app.schemas.adapter import AdapterImportResult, AdapterRead, AdapterSyncResult
from app.services.store_import import import_from_adapter, sync_adapter

router = APIRouter(prefix="/adapters", tags=["adapters"])


def _has_live_source(adapter) -> bool:
    return "list_summaries" in adapter.__class__.__dict__


def _adapter_or_404(key: str):
    adapter = get_adapter(key)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown store adapter '{key}'")
    return adapter


@router.get("", response_model=list[AdapterRead])
def get_adapters() -> list[AdapterRead]:
    return [
        AdapterRead(
            key=adapter.key,
            display_name=adapter.display_name,
            has_live_source=_has_live_source(adapter),
        )
        for adapter in list_adapters()
    ]


@router.post("/{key}/import", response_model=AdapterImportResult, status_code=status.HTTP_201_CREATED)
def import_adapter_receipt(key: str, raw: dict[str, Any], db: Session = Depends(get_db)) -> AdapterImportResult:
    adapter = _adapter_or_404(key)
    try:
        receipt = import_from_adapter(db, adapter, raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return AdapterImportResult(adapter=adapter.key, store_id=receipt.store_id, receipt=receipt)


@router.post("/{key}/sync", response_model=AdapterSyncResult)
def sync_adapter_receipts(key: str, db: Session = Depends(get_db)) -> AdapterSyncResult:
    adapter = _adapter_or_404(key)
    return AdapterSyncResult(**sync_adapter(db, adapter))
