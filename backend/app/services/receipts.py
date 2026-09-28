"""Import receipts and resolve unknown store products by user decision."""

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product, ProductMapping, Purchase, Receipt, ReceiptLine, Store
from app.schemas.product import ProductCreate
from app.schemas.receipt import ReceiptCreate, ReceiptLineRead, ReceiptRead


def _line_read(
    line: ReceiptLine,
    store: Store,
    occurrence_count: int = 1,
    total_package_count: Decimal | None = None,
) -> ReceiptLineRead:
    return ReceiptLineRead(
        id=line.id,
        receipt_id=line.receipt_id,
        store_id=store.id,
        store_name=store.name,
        external_product_id=line.external_product_id,
        name=line.name,
        package_count=line.package_count,
        unit_price=line.unit_price,
        line_total=line.line_total,
        status=line.status,
        purchase_id=line.purchase_id,
        occurrence_count=occurrence_count,
        total_package_count=total_package_count if total_package_count is not None else line.package_count,
        created_at=line.created_at,
    )


def _get_mapping(db: Session, store_id: int, external_product_id: str) -> ProductMapping | None:
    return db.scalar(
        select(ProductMapping).where(
            ProductMapping.store_id == store_id,
            ProductMapping.external_product_id == external_product_id,
        )
    )


def _create_purchase(db: Session, line: ReceiptLine, mapping: ProductMapping, product: Product) -> Purchase:
    purchase = Purchase(
        receipt_id=line.receipt_id,
        product_id=product.id,
        quantity=line.package_count * mapping.package_quantity,
        unit=product.base_unit,
        unit_price=line.unit_price,
        total_price=line.line_total,
    )
    db.add(purchase)
    db.flush()
    line.status = "mapped"
    line.purchase_id = purchase.id
    return purchase


def import_receipt(db: Session, payload: ReceiptCreate) -> ReceiptRead:
    store = db.get(Store, payload.store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    receipt = Receipt(
        store_id=store.id,
        external_receipt_id=payload.external_receipt_id.strip(),
        purchased_at=payload.purchased_at,
        total_price=payload.total_price,
        currency=payload.currency.upper(),
    )
    db.add(receipt)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Receipt with this store and external id already exists",
        ) from None

    lines: list[ReceiptLine] = []
    for item in payload.lines:
        line = ReceiptLine(
            receipt_id=receipt.id,
            external_product_id=item.external_product_id.strip(),
            name=item.name.strip(),
            package_count=item.package_count,
            unit_price=item.unit_price,
            line_total=item.line_total,
            status="unmapped",
        )
        db.add(line)
        db.flush()
        mapping = _get_mapping(db, store.id, line.external_product_id)
        if mapping is not None:
            product = db.get(Product, mapping.product_id)
            if product is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mapped product is missing")
            _create_purchase(db, line, mapping, product)
        lines.append(line)

    db.commit()
    for line in lines:
        db.refresh(line)
    return ReceiptRead(
        id=receipt.id,
        store_id=receipt.store_id,
        external_receipt_id=receipt.external_receipt_id,
        purchased_at=receipt.purchased_at,
        total_price=receipt.total_price,
        currency=receipt.currency,
        mapped_count=sum(1 for line in lines if line.status == "mapped"),
        unmapped_count=sum(1 for line in lines if line.status == "unmapped"),
        lines=[_line_read(line, store) for line in lines],
    )


def list_receipt_lines(db: Session, status_filter: str | None = None) -> list[ReceiptLineRead]:
    stmt = (
        select(ReceiptLine, Store)
        .join(Receipt, Receipt.id == ReceiptLine.receipt_id)
        .join(Store, Store.id == Receipt.store_id)
        .order_by(ReceiptLine.id.asc())
    )
    if status_filter:
        stmt = stmt.where(ReceiptLine.status == status_filter)

    grouped: dict[tuple[int, str, str], list[tuple[ReceiptLine, Store]]] = {}
    for line, store in db.execute(stmt).all():
        key = (store.id, line.external_product_id, line.status)
        grouped.setdefault(key, []).append((line, store))

    items: list[ReceiptLineRead] = []
    for rows in grouped.values():
        line, store = rows[0]
        total_packages = sum((item.package_count for item, _ in rows), Decimal("0"))
        items.append(
            _line_read(
                line,
                store,
                occurrence_count=len(rows),
                total_package_count=total_packages,
            )
        )
    items.sort(key=lambda item: item.id, reverse=True)
    return items


def _create_product(db: Session, payload: ProductCreate) -> Product:
    product = Product(
        name=payload.name,
        base_unit=payload.base_unit,
        minimum_stock=payload.minimum_stock,
    )
    try:
        with db.begin_nested():
            db.add(product)
            db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product with this name already exists. Use /receipt-lines/{id}/resolve with product_id",
        ) from None
    return product


def _apply_mapping_to_unmapped_lines(
    db: Session,
    store_id: int,
    external_product_id: str,
    mapping: ProductMapping,
    product: Product,
) -> None:
    siblings = db.scalars(
        select(ReceiptLine)
        .join(Receipt, Receipt.id == ReceiptLine.receipt_id)
        .where(
            Receipt.store_id == store_id,
            ReceiptLine.external_product_id == external_product_id,
            ReceiptLine.status == "unmapped",
        )
    ).all()
    for sibling in siblings:
        _create_purchase(db, sibling, mapping, product)


def _load_unmapped_line(db: Session, line_id: int) -> tuple[ReceiptLine, Store]:
    line = db.get(ReceiptLine, line_id)
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt line not found")
    if line.status == "mapped":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Receipt line is already mapped")

    receipt = db.get(Receipt, line.receipt_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    store = db.get(Store, receipt.store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return line, store


def _bind_product(
    db: Session,
    line: ReceiptLine,
    store: Store,
    product: Product,
    package_quantity: Decimal | None,
    package_unit: str | None,
) -> ReceiptLineRead:
    mapping = _get_mapping(db, store.id, line.external_product_id)
    if mapping is not None:
        if mapping.product_id != product.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This store product is already mapped to another Product",
            )
    else:
        if package_quantity is None or package_unit is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="package_quantity and package_unit are required for a new mapping",
            )
        if package_unit != product.base_unit:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"package_unit must match product base_unit '{product.base_unit}'",
            )
        mapping = ProductMapping(
            store_id=store.id,
            external_product_id=line.external_product_id,
            product_id=product.id,
            package_quantity=package_quantity,
            package_unit=package_unit,
        )
        db.add(mapping)
        db.flush()

    _apply_mapping_to_unmapped_lines(db, store.id, line.external_product_id, mapping, product)
    db.commit()
    db.refresh(line)
    return _line_read(line, store)


def map_existing_product(
    db: Session,
    line_id: int,
    product_id: int,
    package_quantity: Decimal | None,
    package_unit: str | None,
) -> ReceiptLineRead:
    line, store = _load_unmapped_line(db, line_id)
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return _bind_product(db, line, store, product, package_quantity, package_unit)


def create_product_and_map(
    db: Session,
    line_id: int,
    product_payload: ProductCreate,
    package_quantity: Decimal,
    package_unit: str,
) -> ReceiptLineRead:
    line, store = _load_unmapped_line(db, line_id)
    product = _create_product(db, product_payload)
    return _bind_product(db, line, store, product, package_quantity, package_unit)
