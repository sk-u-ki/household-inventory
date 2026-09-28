"""FastAPI application."""

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.adapters import router as adapters_router
from app.api.inventory import router as inventory_router
from app.api.products import router as products_router
from app.api.purchases import router as purchases_router
from app.api.receipts import receipt_lines_router, receipts_router
from app.api.stores import router as stores_router
from app.config import ROOT_DIR
from app.db import engine, get_db

FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(title="Household Inventory", version="0.1.0")
app.include_router(products_router)
app.include_router(stores_router)
app.include_router(adapters_router)
app.include_router(purchases_router)
app.include_router(receipts_router)
app.include_router(receipt_lines_router)
app.include_router(inventory_router)


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/app/")


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    inspector = inspect(engine)
    return {
        "status": "ok",
        "database": "connected",
        "products_table": inspector.has_table("products"),
    }


if FRONTEND_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

