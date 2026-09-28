"""Registered store adapters. Add a shop by writing a StoreAdapter and registering it."""

from app.adapters.base import NormalizedReceipt, ReceiptSummary, StoreAdapter
from app.adapters.lidl import LidlAdapter
from app.adapters.registry import get_adapter, list_adapters, register

register(LidlAdapter())

__all__ = [
    "LidlAdapter",
    "NormalizedReceipt",
    "ReceiptSummary",
    "StoreAdapter",
    "get_adapter",
    "list_adapters",
    "register",
]
