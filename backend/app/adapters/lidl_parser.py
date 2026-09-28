"""Parse Lidl Plus htmlPrintedReceipt into structured purchase data."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from html import unescape
from html.parser import HTMLParser
from typing import Any


def parse_amount(value: str | None) -> Decimal | None:
    """Parse Polish/EU amounts like '9,99', '-10,00', '19.98'."""
    if value is None:
        return None
    cleaned = unescape(value).replace("\xa0", " ").strip()
    cleaned = re.sub(r"(zł|PLN)", "", cleaned, flags=re.I)
    cleaned = cleaned.replace(" ", "").replace(",", ".")
    if not cleaned or cleaned in {".", "-", "+", "—"}:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


class _SpanCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.spans: list[dict[str, Any]] = []
        self._stack: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "span":
            return
        self._stack.append({"attrs": {k: (unescape(v) if v else v) for k, v in attrs}, "parts": []})

    def handle_data(self, data: str) -> None:
        if self._stack:
            self._stack[-1]["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "span" or not self._stack:
            return
        node = self._stack.pop()
        node["text"] = "".join(node.pop("parts"))
        self.spans.append(node)


def _classes(attrs: dict[str, str | None]) -> set[str]:
    return set((attrs.get("class") or "").split())


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text).replace("\xa0", " ")).strip()


def _discount_from_span(attrs: dict[str, str | None], text: str) -> dict[str, Any]:
    cleaned = _clean_text(text)
    match = re.search(r"^(.*?)\s+(-?\d+[.,]\d{2})$", cleaned)
    name = match.group(1).strip() if match else cleaned
    amount = parse_amount(match.group(2) if match else None)
    return {
        "promotion_id": attrs.get("data-promotion-id"),
        "name": name or None,
        "amount": amount,
    }


def _new_item(attrs: dict[str, str | None]) -> dict[str, Any]:
    quantity = parse_amount(attrs.get("data-art-quantity"))
    unit_price = parse_amount(attrs.get("data-unit-price"))
    line_total = quantity * unit_price if quantity is not None and unit_price is not None else None
    return {
        "id": attrs.get("data-art-id"),
        "name": attrs.get("data-art-description"),
        "quantity": quantity,
        "unit_price": unit_price,
        "tax_type": attrs.get("data-tax-type"),
        "line_total": line_total,
        "discounts": [],
    }


def parse_receipt_html(html: str) -> dict[str, Any]:
    """Extract store, items, discounts, VAT, totals and payment from a Lidl receipt HTML."""
    parser = _SpanCollector()
    parser.feed(html or "")

    items: list[dict[str, Any]] = []
    current_item: dict[str, Any] | None = None
    vat: list[dict[str, Any]] = []
    seen_vat: set[tuple] = set()
    header_lines: list[str] = []
    date = None
    country = None
    language = None
    payment_method = None
    payment_amount = None
    total = None
    saved = None
    return_code = None
    till = None
    receipt_number = None
    time = None

    all_text: list[str] = []

    for span in parser.spans:
        attrs = span["attrs"]
        text = span["text"]
        cleaned = _clean_text(text)
        classes = _classes(attrs)
        span_id = attrs.get("id") or ""
        all_text.append(cleaned)

        if attrs.get("data-till-country"):
            country = attrs["data-till-country"]
        if attrs.get("data-receipt-language"):
            language = attrs["data-receipt-language"]
        if span_id.startswith("header_line_") and cleaned:
            header_lines.append(cleaned)
        if "currency" in classes and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
            date = cleaned

        if "article" in classes and attrs.get("data-art-id"):
            art_id = attrs["data-art-id"]
            if current_item and current_item["id"] == art_id:
                continue
            current_item = _new_item(attrs)
            items.append(current_item)
            continue

        if "discount" in classes:
            discount = _discount_from_span(attrs, text)
            if current_item is not None:
                current_item["discounts"].append(discount)
            continue

        if attrs.get("data-tax-percentage") and attrs.get("data-tax-type"):
            key = (
                attrs.get("data-tax-type"),
                attrs.get("data-tax-percentage"),
                attrs.get("data-tax-base-amount"),
                attrs.get("data-tax-amount"),
            )
            if key not in seen_vat:
                seen_vat.add(key)
                vat.append(
                    {
                        "type": attrs.get("data-tax-type"),
                        "percentage": parse_amount(attrs.get("data-tax-percentage")),
                        "base": parse_amount(attrs.get("data-tax-base-amount")),
                        "amount": parse_amount(attrs.get("data-tax-amount")),
                    }
                )

        if attrs.get("data-tender-description"):
            payment_method = attrs["data-tender-description"]
            payment_amount = parse_amount(cleaned.split()[-1] if cleaned else None)

        if attrs.get("data-return-code"):
            return_code = attrs["data-return-code"]

        if "css_big" in classes and cleaned and parse_amount(cleaned) is not None:
            total = parse_amount(cleaned)

        till_match = re.search(r"(\d+\s+\d+)\s+nr:\s+(\d+)\s+(\d{1,2}:\d{2})", cleaned)
        if till_match:
            till, receipt_number, time = till_match.groups()

    joined = "\n".join(t for t in all_text if t)
    saved_match = re.search(r"zaoszcz[eę]dzono.*?(\d+[.,]\d{2})\s*zł", joined, flags=re.I | re.S)
    if saved_match:
        saved = parse_amount(saved_match.group(1))

    for item in items:
        item["paid"] = item["line_total"]
        if item["paid"] is not None:
            item["paid"] += sum((d["amount"] or Decimal("0")) for d in item["discounts"])

    return {
        "date": date,
        "time": time,
        "country": country,
        "language": language,
        "store": {"address_lines": header_lines},
        "till": till,
        "receipt_number": receipt_number,
        "return_code": return_code,
        "items": items,
        "vat": vat,
        "total": total,
        "saved": saved,
        "payment": {"method": payment_method, "amount": payment_amount},
    }


def parse_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    """Parse a full Lidl Plus ticket payload, using htmlPrintedReceipt when present."""
    parsed = parse_receipt_html(ticket.get("htmlPrintedReceipt") or "")
    parsed["ticket_id"] = ticket.get("id")
    return parsed
