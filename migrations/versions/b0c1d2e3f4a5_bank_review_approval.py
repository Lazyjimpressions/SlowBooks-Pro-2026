"""bank review approval

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
"""

from alembic import op
import sqlalchemy as sa

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("bank_transaction_proposals") as batch_op:
        batch_op.add_column(sa.Column("review_note", sa.Text(), nullable=True))
        batch_op.drop_constraint("ck_bank_proposal_class_resolution", type_="check")
        batch_op.create_check_constraint(
            "ck_bank_proposal_class_resolution",
            "(class_resolution = 'assigned' AND class_id IS NOT NULL) OR "
            "(class_resolution IN ('unresolved', 'personal_no_class', "
            "'not_applicable') AND class_id IS NULL)",
        )


def downgrade():
    with op.batch_alter_table("bank_transaction_proposals") as batch_op:
        batch_op.drop_constraint("ck_bank_proposal_class_resolution", type_="check")
        batch_op.create_check_constraint(
            "ck_bank_proposal_class_resolution",
            "(class_resolution = 'assigned' AND class_id IS NOT NULL) OR "
            "(class_resolution IN ('unresolved', 'personal_no_class') "
            "AND class_id IS NULL)",
        )
        batch_op.drop_column("review_note")
