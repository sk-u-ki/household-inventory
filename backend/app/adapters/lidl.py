"""Lidl Plus ticket → canonical receipt."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.adapters.base import NormalizedLine, NormalizedReceipt, ReceiptSummary, StoreAdapter
from app.adapters.lidl_client import LidlPlusClient
from app.adapters.lidl_parser import parse_ticket

WARSAW = ZoneInfo("Europe/Warsaw")


def _as_decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _purchased_at(ticket: dict[str, Any], parsed: dict[str, Any]) -> datetime:
    raw = ticket.get("date")
    if raw:
        moment = datetime.fromisoformat(str(raw))
        return moment if moment.tzinfo else moment.replace(tzinfo=WARSAW)

    date = parsed.get("date")
    time = parsed.get("time") or "00:00"
    if date:
        moment = datetime.fromisoformat(f"{date}T{time}")
        return moment.replace(tzinfo=WARSAW)

    raise ValueError("Lidl ticket has no date")


class LidlAdapter(StoreAdapter):
    key = "lidl"
    display_name = "Lidl"

    def __init__(self, client: LidlPlusClient | None = None) -> None:
        self._client = client

    def _source(self) -> LidlPlusClient:
        if self._client is None:
            self._client = LidlPlusClient.from_settings()
        return self._client

    def list_summaries(self) -> list[ReceiptSummary]:
        summaries: list[ReceiptSummary] = []
        for item in self._source().tickets():
            ticket_id = str(item.get("id") or "").strip()
            if not ticket_id:
                continue
            purchased_at = None
            raw_date = item.get("date")
            if raw_date:
                moment = datetime.fromisoformat(str(raw_date))
                purchased_at = moment if moment.tzinfo else moment.replace(tzinfo=WARSAW)
            summaries.append(
                ReceiptSummary(
                    external_receipt_id=ticket_id,
                    purchased_at=purchased_at,
                    total_price=_as_decimal(item.get("totalAmount")),
                )
            )
        return summaries

    def fetch_raw(self, external_receipt_id: str) -> dict[str, Any]:
        return self._source().ticket(external_receipt_id)

    def normalize(self, raw: Any) -> NormalizedReceipt:
        if not isinstance(raw, dict):
            raise ValueError("Lidl ticket must be a JSON object")

        ticket_id = str(raw.get("id") or "").strip()
        if not ticket_id:
            raise ValueError("Lidl ticket is missing id")

        parsed = parse_ticket(raw)
        lines: list[NormalizedLine] = []
        for item in parsed.get("items") or []:
            external_id = str(item.get("id") or "").strip()
            name = str(item.get("name") or "").strip()
            if not external_id or not name:
                continue
            package_count = _as_decimal(item.get("quantity"), Decimal("1"))
            unit_price = _as_decimal(item.get("unit_price"), Decimal("0"))
            line_total = _as_decimal(item.get("line_total"), package_count * unit_price)
            if package_count is None or package_count <= 0:
                continue
            lines.append(
                NormalizedLine(
                    external_product_id=external_id,
                    name=name,
                    package_count=package_count,
                    unit_price=unit_price or Decimal("0"),
                    line_total=line_total or Decimal("0"),
                )
            )

        if not lines:
            raise ValueError("Lidl ticket has no products")

        total = _as_decimal(raw.get("totalAmount"), parsed.get("total"))
        if total is None:
            raise ValueError("Lidl ticket is missing total")

        return NormalizedReceipt(
            external_receipt_id=ticket_id,
            purchased_at=_purchased_at(raw, parsed),
            total_price=total,
            currency="PLN",
            lines=lines,
        )
