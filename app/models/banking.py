# ============================================================================
# Bank accounts, bank-feed transactions, and reconciliations.
# ============================================================================

import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Numeric,
    DateTime,
    Boolean,
    Enum,
    ForeignKey,
    CheckConstraint,
    Index,
    JSON,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ReconciliationStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"  # RECON.DAT status byte 0x00
    COMPLETED = "completed"  # status byte 0x01


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    account_id = Column(
        Integer, ForeignKey("accounts.id"), nullable=True
    )  # linked COA account
    bank_name = Column(String(200), nullable=True)
    last_four = Column(String(4), nullable=True)
    balance = Column(Numeric(12, 2), default=0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account = relationship("Account", foreign_keys=[account_id])
    transactions = relationship("BankTransaction", back_populates="bank_account")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, index=True)
    bank_account_id = Column(
        Integer, ForeignKey("bank_accounts.id"), nullable=False, index=True
    )
    date = Column(Date, nullable=False, index=True)
    amount = Column(
        Numeric(12, 2), nullable=False
    )  # positive=deposit, negative=withdrawal
    payee = Column(String(200), nullable=True)
    description = Column(String(500), nullable=True)
    check_number = Column(String(50), nullable=True)
    category_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    reconciled = Column(Boolean, default=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)

    # OFX/QFX import fields (Feature 18)
    import_id = Column(String(100), nullable=True)  # OFX FITID for dedup
    import_source = Column(String(50), nullable=True)  # e.g. "ofx", "qfx"
    match_status = Column(String(20), nullable=True)  # "auto", "manual", "unmatched"

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bank_account = relationship("BankAccount", back_populates="transactions")
    category_account = relationship("Account", foreign_keys=[category_account_id])
    transaction = relationship("Transaction", foreign_keys=[transaction_id])
    proposals = relationship(
        "BankTransactionProposal",
        back_populates="bank_transaction",
        cascade="all, delete-orphan",
        foreign_keys="BankTransactionProposal.bank_transaction_id",
    )


class BankTransactionProposal(Base):
    """Versioned, non-posting classification of imported bank evidence."""

    __tablename__ = "bank_transaction_proposals"
    __table_args__ = (
        UniqueConstraint(
            "bank_transaction_id",
            "revision",
            name="uq_bank_transaction_proposal_revision",
        ),
        CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'posted', 'superseded')",
            name="ck_bank_proposal_status",
        ),
        CheckConstraint(
            "intent IN ('direct_expense', 'direct_income', 'customer_payment', "
            "'bill_payment', 'transfer', 'owner_contribution', 'owner_draw', "
            "'loan_proceeds', 'loan_payment', 'investment_activity', "
            "'reimbursement', 'unknown')",
            name="ck_bank_proposal_intent",
        ),
        CheckConstraint(
            "posting_route IN ('direct', 'transfer', 'customer_payment', "
            "'bill_payment', 'hold')",
            name="ck_bank_proposal_posting_route",
        ),
        CheckConstraint(
            "counterparty_role IS NULL OR counterparty_role IN "
            "('payer', 'payee', 'not_applicable')",
            name="ck_bank_proposal_counterparty_role",
        ),
        CheckConstraint(
            "(counterparty_resolution = 'customer' AND customer_id IS NOT NULL "
            "AND vendor_id IS NULL) OR (counterparty_resolution = 'vendor' "
            "AND vendor_id IS NOT NULL AND customer_id IS NULL) OR "
            "(counterparty_resolution IN ('unresolved', 'text_only', "
            "'not_applicable') AND customer_id IS NULL AND vendor_id IS NULL)",
            name="ck_bank_proposal_counterparty_resolution",
        ),
        CheckConstraint(
            "(class_resolution = 'assigned' AND class_id IS NOT NULL) OR "
            "(class_resolution IN ('unresolved', 'personal_no_class', "
            "'not_applicable') "
            "AND class_id IS NULL)",
            name="ck_bank_proposal_class_resolution",
        ),
        CheckConstraint(
            "proposal_source IN ('human', 'rule', 'deterministic', 'ai')",
            name="ck_bank_proposal_source",
        ),
        CheckConstraint("revision > 0", name="ck_bank_proposal_revision_positive"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_bank_proposal_confidence",
        ),
        Index(
            "uq_bank_transaction_proposal_active",
            "bank_transaction_id",
            unique=True,
            sqlite_where=text("status IN ('proposed', 'approved')"),
            postgresql_where=text("status IN ('proposed', 'approved')"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    bank_transaction_id = Column(
        Integer,
        ForeignKey("bank_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="proposed")
    intent = Column(String(30), nullable=False, default="unknown")
    posting_route = Column(String(30), nullable=False, default="hold")

    normalized_counterparty = Column(String(200), nullable=True)
    normalized_counterparty_key = Column(String(200), nullable=True, index=True)
    counterparty_role = Column(String(20), nullable=True)
    counterparty_resolution = Column(String(20), nullable=False, default="unresolved")
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    counter_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    class_resolution = Column(String(30), nullable=False, default="unresolved")
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)

    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=True)
    paired_bank_transaction_id = Column(
        Integer, ForeignKey("bank_transactions.id"), nullable=True
    )

    proposal_source = Column(String(20), nullable=False, default="human")
    confidence = Column(Numeric(5, 4), nullable=True)
    confidence_components = Column(JSON, nullable=True)
    rationale = Column(Text, nullable=True)
    review_note = Column(Text, nullable=True)
    normalizer_version = Column(String(50), nullable=True)
    supersedes_id = Column(
        Integer, ForeignKey("bank_transaction_proposals.id"), nullable=True
    )

    created_by = Column(String(200), nullable=False)
    reviewed_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)

    bank_transaction = relationship(
        "BankTransaction",
        back_populates="proposals",
        foreign_keys=[bank_transaction_id],
    )
    paired_bank_transaction = relationship(
        "BankTransaction", foreign_keys=[paired_bank_transaction_id]
    )
    customer = relationship("Customer", foreign_keys=[customer_id])
    vendor = relationship("Vendor", foreign_keys=[vendor_id])
    counter_account = relationship("Account", foreign_keys=[counter_account_id])
    txn_class = relationship("TxnClass", foreign_keys=[class_id])
    invoice = relationship("Invoice", foreign_keys=[invoice_id])
    bill = relationship("Bill", foreign_keys=[bill_id])
    supersedes = relationship(
        "BankTransactionProposal", remote_side=[id], foreign_keys=[supersedes_id]
    )


class BankCounterpartyAlias(Base):
    """Reviewed exact mapping from normalized bank text to a counterparty."""

    __tablename__ = "bank_counterparty_aliases"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('any', 'deposit', 'withdrawal')",
            name="ck_bank_alias_direction",
        ),
        CheckConstraint(
            "(customer_id IS NOT NULL AND vendor_id IS NULL) OR "
            "(vendor_id IS NOT NULL AND customer_id IS NULL) OR "
            "(customer_id IS NULL AND vendor_id IS NULL)",
            name="ck_bank_alias_contact_exclusive",
        ),
        CheckConstraint(
            "counterparty_role IN ('payer', 'payee', 'not_applicable')",
            name="ck_bank_alias_counterparty_role",
        ),
        CheckConstraint(
            "counterparty_role != 'not_applicable' OR "
            "(customer_id IS NULL AND vendor_id IS NULL)",
            name="ck_bank_alias_not_applicable_contact",
        ),
        Index(
            "uq_bank_alias_global",
            "normalized_pattern",
            "direction",
            unique=True,
            sqlite_where=text("is_active = true AND bank_account_id IS NULL"),
            postgresql_where=text("is_active = true AND bank_account_id IS NULL"),
        ),
        Index(
            "uq_bank_alias_scoped",
            "bank_account_id",
            "normalized_pattern",
            "direction",
            unique=True,
            sqlite_where=text("is_active = true AND bank_account_id IS NOT NULL"),
            postgresql_where=text("is_active = true AND bank_account_id IS NOT NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    pattern = Column(String(500), nullable=False)
    normalized_pattern = Column(String(200), nullable=False, index=True)
    canonical_name = Column(String(200), nullable=False)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=True)
    direction = Column(String(20), nullable=False, default="any")
    counterparty_role = Column(String(20), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    default_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    default_class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    normalizer_version = Column(String(50), nullable=False)
    created_by = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bank_account = relationship("BankAccount", foreign_keys=[bank_account_id])
    customer = relationship("Customer", foreign_keys=[customer_id])
    vendor = relationship("Vendor", foreign_keys=[vendor_id])
    default_account = relationship("Account", foreign_keys=[default_account_id])
    default_class = relationship("TxnClass", foreign_keys=[default_class_id])


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id = Column(Integer, primary_key=True, index=True)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False)
    statement_date = Column(Date, nullable=False)
    statement_balance = Column(Numeric(12, 2), nullable=False)
    status = Column(
        Enum(ReconciliationStatus), default=ReconciliationStatus.IN_PROGRESS
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    bank_account = relationship("BankAccount")
