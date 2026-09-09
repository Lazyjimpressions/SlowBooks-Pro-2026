"""bank review proposals

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
"""

from alembic import op
import sqlalchemy as sa

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bank_transaction_proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bank_transaction_id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("intent", sa.String(length=30), nullable=False),
        sa.Column("posting_route", sa.String(length=30), nullable=False),
        sa.Column("normalized_counterparty", sa.String(length=200), nullable=True),
        sa.Column("counterparty_role", sa.String(length=20), nullable=True),
        sa.Column("counterparty_resolution", sa.String(length=20), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("counter_account_id", sa.Integer(), nullable=True),
        sa.Column("class_resolution", sa.String(length=30), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=True),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column("bill_id", sa.Integer(), nullable=True),
        sa.Column("paired_bank_transaction_id", sa.Integer(), nullable=True),
        sa.Column("proposal_source", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("normalizer_version", sa.String(length=50), nullable=True),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("reviewed_by", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'posted', 'superseded')",
            name="ck_bank_proposal_status",
        ),
        sa.CheckConstraint(
            "intent IN ('direct_expense', 'direct_income', 'customer_payment', "
            "'bill_payment', 'transfer', 'owner_contribution', 'owner_draw', "
            "'loan_proceeds', 'loan_payment', 'investment_activity', "
            "'reimbursement', 'unknown')",
            name="ck_bank_proposal_intent",
        ),
        sa.CheckConstraint(
            "posting_route IN ('direct', 'transfer', 'customer_payment', "
            "'bill_payment', 'hold')",
            name="ck_bank_proposal_posting_route",
        ),
        sa.CheckConstraint(
            "counterparty_role IS NULL OR counterparty_role IN "
            "('payer', 'payee', 'not_applicable')",
            name="ck_bank_proposal_counterparty_role",
        ),
        sa.CheckConstraint(
            "(counterparty_resolution = 'customer' AND customer_id IS NOT NULL "
            "AND vendor_id IS NULL) OR (counterparty_resolution = 'vendor' "
            "AND vendor_id IS NOT NULL AND customer_id IS NULL) OR "
            "(counterparty_resolution IN ('unresolved', 'text_only', "
            "'not_applicable') AND customer_id IS NULL AND vendor_id IS NULL)",
            name="ck_bank_proposal_counterparty_resolution",
        ),
        sa.CheckConstraint(
            "(class_resolution = 'assigned' AND class_id IS NOT NULL) OR "
            "(class_resolution IN ('unresolved', 'personal_no_class') "
            "AND class_id IS NULL)",
            name="ck_bank_proposal_class_resolution",
        ),
        sa.CheckConstraint(
            "proposal_source IN ('human', 'rule', 'deterministic', 'ai')",
            name="ck_bank_proposal_source",
        ),
        sa.CheckConstraint("revision > 0", name="ck_bank_proposal_revision_positive"),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_bank_proposal_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["bank_transaction_id"], ["bank_transactions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"]),
        sa.ForeignKeyConstraint(["counter_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"]),
        sa.ForeignKeyConstraint(
            ["paired_bank_transaction_id"], ["bank_transactions.id"]
        ),
        sa.ForeignKeyConstraint(["supersedes_id"], ["bank_transaction_proposals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bank_transaction_id",
            "revision",
            name="uq_bank_transaction_proposal_revision",
        ),
    )
    op.create_index(
        "ix_bank_transaction_proposals_id",
        "bank_transaction_proposals",
        ["id"],
    )
    op.create_index(
        "ix_bank_transaction_proposals_bank_transaction_id",
        "bank_transaction_proposals",
        ["bank_transaction_id"],
    )
    op.create_index(
        "uq_bank_transaction_proposal_active",
        "bank_transaction_proposals",
        ["bank_transaction_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('proposed', 'approved')"),
        postgresql_where=sa.text("status IN ('proposed', 'approved')"),
    )


def downgrade():
    op.drop_index(
        "uq_bank_transaction_proposal_active",
        table_name="bank_transaction_proposals",
    )
    op.drop_index(
        "ix_bank_transaction_proposals_bank_transaction_id",
        table_name="bank_transaction_proposals",
    )
    op.drop_index(
        "ix_bank_transaction_proposals_id",
        table_name="bank_transaction_proposals",
    )
    op.drop_table("bank_transaction_proposals")
