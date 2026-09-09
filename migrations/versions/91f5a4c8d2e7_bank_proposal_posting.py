"""approved bank proposal posting and counterparty provenance

Revision ID: 91f5a4c8d2e7
Revises: b0c1d2e3f4a5
"""

from alembic import op
import sqlalchemy as sa

revision = "91f5a4c8d2e7"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("uq_transactions_bank_source", table_name="transactions")
    op.create_index(
        "uq_transactions_bank_source",
        "transactions",
        ["source_type", "source_id"],
        unique=True,
        sqlite_where=sa.text(
            "source_type IN ('bank_feed', 'bank_transfer', 'bank_expense', "
            "'bank_income', 'bank_activity', 'bank_proposal_transfer', "
            "'bank_proposal_reversal')"
        ),
        postgresql_where=sa.text(
            "source_type IN ('bank_feed', 'bank_transfer', 'bank_expense', "
            "'bank_income', 'bank_activity', 'bank_proposal_transfer', "
            "'bank_proposal_reversal')"
        ),
    )
    with op.batch_alter_table("bank_transaction_proposals") as batch_op:
        batch_op.add_column(
            sa.Column("posted_transaction_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("reversal_transaction_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(sa.Column("reversed_by", sa.String(200), nullable=True))
        batch_op.add_column(
            sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_bank_proposal_posted_transaction",
            "transactions",
            ["posted_transaction_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_bank_proposal_reversal_transaction",
            "transactions",
            ["reversal_transaction_id"],
            ["id"],
        )
        batch_op.drop_constraint("ck_bank_proposal_status", type_="check")
        batch_op.create_check_constraint(
            "ck_bank_proposal_status",
            "status IN ('proposed', 'approved', 'rejected', 'posted', "
            "'reversed', 'superseded')",
        )

    op.create_table(
        "transaction_counterparties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("proposal_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "role IN ('payer', 'payee')", name="ck_transaction_counterparty_role"
        ),
        sa.CheckConstraint(
            "NOT (customer_id IS NOT NULL AND vendor_id IS NOT NULL)",
            name="ck_transaction_counterparty_contact_exclusive",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"]),
        sa.ForeignKeyConstraint(["proposal_id"], ["bank_transaction_proposals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id"),
        sa.UniqueConstraint("proposal_id"),
    )
    op.create_index(
        "ix_transaction_counterparties_id", "transaction_counterparties", ["id"]
    )


def downgrade():
    op.drop_index(
        "ix_transaction_counterparties_id", table_name="transaction_counterparties"
    )
    op.drop_table("transaction_counterparties")

    with op.batch_alter_table("bank_transaction_proposals") as batch_op:
        batch_op.drop_constraint("ck_bank_proposal_status", type_="check")
        batch_op.create_check_constraint(
            "ck_bank_proposal_status",
            "status IN ('proposed', 'approved', 'rejected', 'posted', 'superseded')",
        )
        batch_op.drop_constraint(
            "fk_bank_proposal_reversal_transaction", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_bank_proposal_posted_transaction", type_="foreignkey"
        )
        batch_op.drop_column("reversed_at")
        batch_op.drop_column("reversed_by")
        batch_op.drop_column("reversal_transaction_id")
        batch_op.drop_column("posted_transaction_id")

    op.drop_index("uq_transactions_bank_source", table_name="transactions")
    op.create_index(
        "uq_transactions_bank_source",
        "transactions",
        ["source_type", "source_id"],
        unique=True,
        sqlite_where=sa.text("source_type IN ('bank_feed', 'bank_transfer')"),
        postgresql_where=sa.text("source_type IN ('bank_feed', 'bank_transfer')"),
    )
