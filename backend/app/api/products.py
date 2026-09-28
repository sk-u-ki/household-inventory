"""Product HTTP routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, ProductMapping, Purchase
from app.schemas import ProductCreate, ProductRead, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
def list_products(db: Session = Depends(get_db)) -> list[Product]:
    return list(db.scalars(select(Product).order_by(Product.name)).all())


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> Product:
    product = Product(
        name=payload.name,
        base_unit=payload.base_unit,
        minimum_stock=payload.minimum_stock,
    )
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product with this name already exists",
        ) from None
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return product

    if "base_unit" in changes and changes["base_unit"] != product.base_unit:
        used = db.scalar(select(Purchase.id).where(Purchase.product_id == product.id).limit(1))
        mapped = db.scalar(select(ProductMapping.id).where(ProductMapping.product_id == product.id).limit(1))
        if used is not None or mapped is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot change unit after purchases or store mappings exist",
            )

    if "name" in changes:
        product.name = changes["name"]
    if "base_unit" in changes:
        product.base_unit = changes["base_unit"]
    if "minimum_stock" in changes:
        product.minimum_stock = changes["minimum_stock"]

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product with this name already exists",
        ) from None
    db.refresh(product)
    return product
