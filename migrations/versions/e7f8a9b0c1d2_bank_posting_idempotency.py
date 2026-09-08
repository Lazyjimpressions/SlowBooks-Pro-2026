"""bank posting idempotency

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
"""

from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_transactions_bank_source",
        "transactions",
        ["source_type", "source_id"],
        unique=True,
        sqlite_where=sa.text("source_type IN ('bank_feed', 'bank_transfer')"),
        postgresql_where=sa.text("source_type IN ('bank_feed', 'bank_transfer')"),
    )


def downgrade():
    op.drop_index("uq_transactions_bank_source", table_name="transactions")
