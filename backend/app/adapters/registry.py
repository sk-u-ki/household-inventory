"""In-process registry of store adapters."""

from app.adapters.base import StoreAdapter

_adapters: dict[str, StoreAdapter] = {}


def register(adapter: StoreAdapter) -> None:
    _adapters[adapter.key] = adapter


def get_adapter(key: str) -> StoreAdapter | None:
    return _adapters.get(key)


def list_adapters() -> list[StoreAdapter]:
    return list(_adapters.values())
