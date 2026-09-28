"""drop persistent ignored SKUs; skip is one-time only

Revision ID: 005_drop_ignored_skus
Revises: 004_ignore_skus
Create Date: 2026-09-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_drop_ignored_skus"
down_revision: Union[str, Sequence[str], None] = "004_ignore_skus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("ignored_skus")


def downgrade() -> None:
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
