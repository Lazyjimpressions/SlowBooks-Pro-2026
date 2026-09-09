"""expand bank rules into reviewed proposal memory

Revision ID: 2c7d9e1f4a6b
Revises: 91f5a4c8d2e7
"""

from alembic import op
import sqlalchemy as sa

revision = "2c7d9e1f4a6b"
down_revision = "91f5a4c8d2e7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("bank_rules") as batch_op:
        batch_op.add_column(sa.Column("customer_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("bank_account_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("class_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "match_field", sa.String(20), nullable=False, server_default="raw"
            )
        )
        batch_op.add_column(
            sa.Column("direction", sa.String(20), nullable=False, server_default="any")
        )
        batch_op.add_column(sa.Column("minimum_amount", sa.Numeric(12, 2)))
        batch_op.add_column(sa.Column("maximum_amount", sa.Numeric(12, 2)))
        batch_op.add_column(sa.Column("intent", sa.String(30)))
        batch_op.add_column(sa.Column("posting_route", sa.String(30)))
        batch_op.add_column(sa.Column("counterparty_role", sa.String(20)))
        batch_op.add_column(sa.Column("counterparty_resolution", sa.String(20)))
        batch_op.add_column(sa.Column("class_resolution", sa.String(30)))
        batch_op.create_foreign_key(
            "fk_bank_rule_customer", "customers", ["customer_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_bank_rule_bank_account",
            "bank_accounts",
            ["bank_account_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_bank_rule_class", "classes", ["class_id"], ["id"]
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_type",
            "rule_type IN ('contains', 'starts_with', 'exact')",
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_match_field", "match_field IN ('raw', 'normalized')"
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_direction", "direction IN ('any', 'deposit', 'withdrawal')"
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_minimum_amount",
            "minimum_amount IS NULL OR minimum_amount >= 0",
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_maximum_amount",
            "maximum_amount IS NULL OR maximum_amount >= 0",
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_amount_range",
            "minimum_amount IS NULL OR maximum_amount IS NULL OR "
            "minimum_amount <= maximum_amount",
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_contact_exclusive",
            "NOT (customer_id IS NOT NULL AND vendor_id IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_intent",
            "intent IS NULL OR intent IN ('direct_expense', 'direct_income', "
            "'customer_payment', 'bill_payment', 'transfer', 'owner_contribution', "
            "'owner_draw', 'loan_proceeds', 'loan_payment', 'investment_activity', "
            "'reimbursement', 'unknown')",
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_posting_route",
            "posting_route IS NULL OR posting_route IN ('direct', 'transfer', "
            "'customer_payment', 'bill_payment', 'hold')",
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_counterparty_role",
            "counterparty_role IS NULL OR counterparty_role IN "
            "('payer', 'payee', 'not_applicable')",
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_counterparty_resolution",
            "counterparty_resolution IS NULL OR counterparty_resolution IN "
            "('unresolved', 'text_only', 'customer', 'vendor', 'not_applicable')",
        )
        batch_op.create_check_constraint(
            "ck_bank_rule_class_resolution",
            "class_resolution IS NULL OR class_resolution IN "
            "('unresolved', 'personal_no_class', 'assigned', 'not_applicable')",
        )


def downgrade():
    with op.batch_alter_table("bank_rules") as batch_op:
        for name in (
            "ck_bank_rule_class_resolution",
            "ck_bank_rule_counterparty_resolution",
            "ck_bank_rule_counterparty_role",
            "ck_bank_rule_posting_route",
            "ck_bank_rule_intent",
            "ck_bank_rule_contact_exclusive",
            "ck_bank_rule_amount_range",
            "ck_bank_rule_maximum_amount",
            "ck_bank_rule_minimum_amount",
            "ck_bank_rule_direction",
            "ck_bank_rule_match_field",
            "ck_bank_rule_type",
        ):
            batch_op.drop_constraint(name, type_="check")
        batch_op.drop_constraint("fk_bank_rule_class", type_="foreignkey")
        batch_op.drop_constraint("fk_bank_rule_bank_account", type_="foreignkey")
        batch_op.drop_constraint("fk_bank_rule_customer", type_="foreignkey")
        for column in (
            "class_resolution",
            "counterparty_resolution",
            "counterparty_role",
            "posting_route",
            "intent",
            "maximum_amount",
            "minimum_amount",
            "direction",
            "match_field",
            "class_id",
            "bank_account_id",
            "customer_id",
        ):
            batch_op.drop_column(column)
