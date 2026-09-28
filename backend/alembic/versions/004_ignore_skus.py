"""ignored store SKUs and receipt_line status ignored

Revision ID: 004_ignore_skus
Revises: 003_create_receipt_lines
Create Date: 2026-09-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_ignore_skus"
down_revision: Union[str, Sequence[str], None] = "003_create_receipt_lines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ignored_skus",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("store_id", sa.BigInteger(), nullable=False),
        sa.Column("external_product_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "external_product_id", name="uq_ignored_skus_store_external"),
    )
    op.drop_constraint("ck_receipt_lines_status", "receipt_lines", type_="check")
    op.create_check_constraint(
        "ck_receipt_lines_status",
        "receipt_lines",
        "status IN ('unmapped', 'mapped', 'ignored')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_receipt_lines_status", "receipt_lines", type_="check")
    op.create_check_constraint(
        "ck_receipt_lines_status",
        "receipt_lines",
        "status IN ('unmapped', 'mapped')",
    )
    op.drop_table("ignored_skus")
