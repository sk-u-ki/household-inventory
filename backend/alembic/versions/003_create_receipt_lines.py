"""create receipt_lines and unique mapping constraints

Revision ID: 003_create_receipt_lines
Revises: 2b293a9fd181
Create Date: 2026-09-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_create_receipt_lines"
down_revision: Union[str, Sequence[str], None] = "2b293a9fd181"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_product_mappings_store_external", "product_mappings", ["store_id", "external_product_id"])
    op.create_unique_constraint("uq_receipts_store_external", "receipts", ["store_id", "external_receipt_id"])
    op.create_table(
        "receipt_lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("receipt_id", sa.BigInteger(), nullable=False),
        sa.Column("external_product_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("package_count", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.Text(), server_default="unmapped", nullable=False),
        sa.Column("purchase_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('unmapped', 'mapped')", name="ck_receipt_lines_status"),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.id"]),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("receipt_lines")
    op.drop_constraint("uq_receipts_store_external", "receipts", type_="unique")
    op.drop_constraint("uq_product_mappings_store_external", "product_mappings", type_="unique")
