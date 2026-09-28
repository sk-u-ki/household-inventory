"""HTTP schemas for store adapters."""

from pydantic import BaseModel

from app.schemas.receipt import ReceiptRead


class AdapterRead(BaseModel):
    key: str
    display_name: str
    has_live_source: bool


class AdapterImportResult(BaseModel):
    adapter: str
    store_id: int
    receipt: ReceiptRead


class AdapterSyncResult(BaseModel):
    adapter: str
    store_id: int
    imported: int
    skipped: int
    failed: int
    errors: list[str]
