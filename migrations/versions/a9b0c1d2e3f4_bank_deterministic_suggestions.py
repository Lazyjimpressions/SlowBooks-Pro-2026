"""bank deterministic suggestions

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
"""

from alembic import op
import sqlalchemy as sa

revision = "a9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bank_transaction_proposals",
        sa.Column("normalized_counterparty_key", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "bank_transaction_proposals",
        sa.Column("confidence_components", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_bank_transaction_proposals_normalized_counterparty_key",
        "bank_transaction_proposals",
        ["normalized_counterparty_key"],
    )

    op.create_table(
        "bank_counterparty_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern", sa.String(length=500), nullable=False),
        sa.Column("normalized_pattern", sa.String(length=200), nullable=False),
        sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("counterparty_role", sa.String(length=20), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("default_account_id", sa.Integer(), nullable=True),
        sa.Column("default_class_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("normalizer_version", sa.String(length=50), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "direction IN ('any', 'deposit', 'withdrawal')",
            name="ck_bank_alias_direction",
        ),
        sa.CheckConstraint(
            "(customer_id IS NOT NULL AND vendor_id IS NULL) OR "
            "(vendor_id IS NOT NULL AND customer_id IS NULL) OR "
            "(customer_id IS NULL AND vendor_id IS NULL)",
            name="ck_bank_alias_contact_exclusive",
        ),
        sa.CheckConstraint(
            "counterparty_role IN ('payer', 'payee', 'not_applicable')",
            name="ck_bank_alias_counterparty_role",
        ),
        sa.CheckConstraint(
            "counterparty_role != 'not_applicable' OR "
            "(customer_id IS NULL AND vendor_id IS NULL)",
            name="ck_bank_alias_not_applicable_contact",
        ),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"]),
        sa.ForeignKeyConstraint(["default_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["default_class_id"], ["classes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bank_counterparty_aliases_id",
        "bank_counterparty_aliases",
        ["id"],
    )
    op.create_index(
        "ix_bank_counterparty_aliases_normalized_pattern",
        "bank_counterparty_aliases",
        ["normalized_pattern"],
    )
    op.create_index(
        "uq_bank_alias_global",
        "bank_counterparty_aliases",
        ["normalized_pattern", "direction"],
        unique=True,
        sqlite_where=sa.text("is_active = true AND bank_account_id IS NULL"),
        postgresql_where=sa.text("is_active = true AND bank_account_id IS NULL"),
    )
    op.create_index(
        "uq_bank_alias_scoped",
        "bank_counterparty_aliases",
        ["bank_account_id", "normalized_pattern", "direction"],
        unique=True,
        sqlite_where=sa.text("is_active = true AND bank_account_id IS NOT NULL"),
        postgresql_where=sa.text("is_active = true AND bank_account_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index("uq_bank_alias_scoped", table_name="bank_counterparty_aliases")
    op.drop_index("uq_bank_alias_global", table_name="bank_counterparty_aliases")
    op.drop_index(
        "ix_bank_counterparty_aliases_normalized_pattern",
        table_name="bank_counterparty_aliases",
    )
    op.drop_index(
        "ix_bank_counterparty_aliases_id", table_name="bank_counterparty_aliases"
    )
    op.drop_table("bank_counterparty_aliases")

    op.drop_index(
        "ix_bank_transaction_proposals_normalized_counterparty_key",
        table_name="bank_transaction_proposals",
    )
    op.drop_column("bank_transaction_proposals", "confidence_components")
    op.drop_column("bank_transaction_proposals", "normalized_counterparty_key")
