"""Raw store receipt line waiting for user mapping."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ReceiptLine(Base):
    __tablename__ = "receipt_lines"
    __table_args__ = (CheckConstraint("status IN ('unmapped', 'mapped')", name="ck_receipt_lines_status"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    receipt_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("receipts.id"), nullable=False)
    external_product_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    package_count: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unmapped")
    purchase_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("purchases.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
