# ============================================================================
# Bank Rules — auto-categorize imported transactions by payee pattern
# Phase 10: Quick Wins + Medium Effort Features
# ============================================================================

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)

from app.database import Base


class BankRule(Base):
    __tablename__ = "bank_rules"
    __table_args__ = (
        CheckConstraint(
            "rule_type IN ('contains', 'starts_with', 'exact')",
            name="ck_bank_rule_type",
        ),
        CheckConstraint(
            "match_field IN ('raw', 'normalized')",
            name="ck_bank_rule_match_field",
        ),
        CheckConstraint(
            "direction IN ('any', 'deposit', 'withdrawal')",
            name="ck_bank_rule_direction",
        ),
        CheckConstraint(
            "minimum_amount IS NULL OR minimum_amount >= 0",
            name="ck_bank_rule_minimum_amount",
        ),
        CheckConstraint(
            "maximum_amount IS NULL OR maximum_amount >= 0",
            name="ck_bank_rule_maximum_amount",
        ),
        CheckConstraint(
            "minimum_amount IS NULL OR maximum_amount IS NULL OR "
            "minimum_amount <= maximum_amount",
            name="ck_bank_rule_amount_range",
        ),
        CheckConstraint(
            "NOT (customer_id IS NOT NULL AND vendor_id IS NOT NULL)",
            name="ck_bank_rule_contact_exclusive",
        ),
        CheckConstraint(
            "intent IS NULL OR intent IN ('direct_expense', 'direct_income', "
            "'customer_payment', 'bill_payment', 'transfer', 'owner_contribution', "
            "'owner_draw', 'loan_proceeds', 'loan_payment', 'investment_activity', "
            "'reimbursement', 'unknown')",
            name="ck_bank_rule_intent",
        ),
        CheckConstraint(
            "posting_route IS NULL OR posting_route IN ('direct', 'transfer', "
            "'customer_payment', 'bill_payment', 'hold')",
            name="ck_bank_rule_posting_route",
        ),
        CheckConstraint(
            "counterparty_role IS NULL OR counterparty_role IN "
            "('payer', 'payee', 'not_applicable')",
            name="ck_bank_rule_counterparty_role",
        ),
        CheckConstraint(
            "counterparty_resolution IS NULL OR counterparty_resolution IN "
            "('unresolved', 'text_only', 'customer', 'vendor', 'not_applicable')",
            name="ck_bank_rule_counterparty_resolution",
        ),
        CheckConstraint(
            "class_resolution IS NULL OR class_resolution IN "
            "('unresolved', 'personal_no_class', 'assigned', 'not_applicable')",
            name="ck_bank_rule_class_resolution",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    pattern = Column(String(200), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    rule_type = Column(String(20), default="contains")  # contains, starts_with, exact
    match_field = Column(String(20), nullable=False, default="raw")
    direction = Column(String(20), nullable=False, default="any")
    minimum_amount = Column(Numeric(12, 2), nullable=True)
    maximum_amount = Column(Numeric(12, 2), nullable=True)
    intent = Column(String(30), nullable=True)
    posting_route = Column(String(30), nullable=True)
    counterparty_role = Column(String(20), nullable=True)
    counterparty_resolution = Column(String(20), nullable=True)
    class_resolution = Column(String(30), nullable=True)
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
