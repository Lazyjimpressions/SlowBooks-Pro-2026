from datetime import date as dt_date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator
from app.schemas.common import StrictModel

from app.models.banking import ReconciliationStatus


class BankAccountCreate(StrictModel):
    name: str
    account_id: Optional[int] = None
    bank_name: Optional[str] = None
    last_four: Optional[str] = None
    balance: Decimal = Decimal("0")


class BankAccountUpdate(StrictModel):
    name: Optional[str] = None
    account_id: Optional[int] = None
    bank_name: Optional[str] = None
    last_four: Optional[str] = None
    is_active: Optional[bool] = None


class BankAccountResponse(BaseModel):
    id: int
    name: str
    account_id: Optional[int]
    bank_name: Optional[str]
    last_four: Optional[str]
    balance: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BankTransactionCreate(StrictModel):
    bank_account_id: int
    date: dt_date
    amount: Decimal
    payee: Optional[str] = None
    description: Optional[str] = None
    check_number: Optional[str] = None
    category_account_id: Optional[int] = None


class BankTransactionResponse(BaseModel):
    id: int
    bank_account_id: int
    date: dt_date
    amount: Decimal
    payee: Optional[str]
    description: Optional[str]
    check_number: Optional[str]
    category_account_id: Optional[int]
    transaction_id: Optional[int]
    match_status: Optional[str]
    reconciled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


BankProposalIntent = Literal[
    "direct_expense",
    "direct_income",
    "customer_payment",
    "bill_payment",
    "transfer",
    "owner_contribution",
    "owner_draw",
    "loan_proceeds",
    "loan_payment",
    "investment_activity",
    "reimbursement",
    "unknown",
]
BankProposalRoute = Literal[
    "direct", "transfer", "customer_payment", "bill_payment", "hold"
]
CounterpartyResolution = Literal[
    "unresolved", "text_only", "customer", "vendor", "not_applicable"
]
CounterpartyRole = Literal["payer", "payee", "not_applicable"]
ClassResolution = Literal[
    "unresolved", "personal_no_class", "assigned", "not_applicable"
]
ProposalSource = Literal["human", "rule", "deterministic", "ai"]


class BankTransactionProposalCreate(StrictModel):
    intent: BankProposalIntent = "unknown"
    posting_route: BankProposalRoute = "hold"
    normalized_counterparty: Optional[str] = Field(default=None, max_length=200)
    counterparty_role: Optional[CounterpartyRole] = None
    counterparty_resolution: CounterpartyResolution = "unresolved"
    customer_id: Optional[int] = None
    vendor_id: Optional[int] = None
    counter_account_id: Optional[int] = None
    class_resolution: ClassResolution = "unresolved"
    class_id: Optional[int] = None
    invoice_id: Optional[int] = None
    bill_id: Optional[int] = None
    paired_bank_transaction_id: Optional[int] = None
    proposal_source: ProposalSource = "human"
    confidence: Optional[Decimal] = None
    rationale: Optional[str] = None
    normalizer_version: Optional[str] = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_resolutions(self):
        if self.class_resolution == "assigned" and self.class_id is None:
            raise ValueError("class_id is required when class_resolution is assigned")
        if self.class_resolution != "assigned" and self.class_id is not None:
            raise ValueError(
                "class_id is only allowed when class_resolution is assigned"
            )

        if self.counterparty_resolution == "customer":
            if self.customer_id is None or self.vendor_id is not None:
                raise ValueError(
                    "customer resolution requires customer_id and forbids vendor_id"
                )
        elif self.counterparty_resolution == "vendor":
            if self.vendor_id is None or self.customer_id is not None:
                raise ValueError(
                    "vendor resolution requires vendor_id and forbids customer_id"
                )
        elif self.customer_id is not None or self.vendor_id is not None:
            raise ValueError(
                "customer_id and vendor_id require their matching resolution"
            )

        if self.confidence is not None and not Decimal(
            "0"
        ) <= self.confidence <= Decimal("1"):
            raise ValueError("confidence must be between 0 and 1")
        if self.invoice_id is not None and self.bill_id is not None:
            raise ValueError("a proposal cannot reference both an invoice and a bill")
        return self


class BankTransactionProposalResponse(BaseModel):
    id: int
    bank_transaction_id: int
    revision: int
    status: str
    intent: str
    posting_route: str
    normalized_counterparty: Optional[str]
    normalized_counterparty_key: Optional[str]
    counterparty_role: Optional[str]
    counterparty_resolution: str
    customer_id: Optional[int]
    vendor_id: Optional[int]
    counter_account_id: Optional[int]
    class_resolution: str
    class_id: Optional[int]
    invoice_id: Optional[int]
    bill_id: Optional[int]
    paired_bank_transaction_id: Optional[int]
    proposal_source: str
    confidence: Optional[Decimal]
    confidence_components: Optional[list[dict]]
    rationale: Optional[str]
    review_note: Optional[str]
    normalizer_version: Optional[str]
    supersedes_id: Optional[int]
    created_by: str
    reviewed_by: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]
    posted_at: Optional[datetime]

    model_config = {"from_attributes": True}


class BankReviewQueueItem(BaseModel):
    transaction: BankTransactionResponse
    active_proposal: Optional[BankTransactionProposalResponse]


class BankTransactionReviewResponse(BankReviewQueueItem):
    proposal_history: list[BankTransactionProposalResponse]


class BankProposalReviewAction(StrictModel):
    note: Optional[str] = Field(default=None, max_length=1000)


class BankProposalBulkApprove(StrictModel):
    proposal_ids: list[int] = Field(min_length=2, max_length=100)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        if len(set(self.proposal_ids)) != len(self.proposal_ids):
            raise ValueError("proposal_ids must be unique")
        return self


class BankCounterpartyAliasCreate(StrictModel):
    pattern: str = Field(min_length=1, max_length=500)
    canonical_name: str = Field(min_length=1, max_length=200)
    bank_account_id: Optional[int] = None
    direction: Literal["any", "deposit", "withdrawal"] = "any"
    counterparty_role: CounterpartyRole
    customer_id: Optional[int] = None
    vendor_id: Optional[int] = None
    default_account_id: Optional[int] = None
    default_class_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.pattern.strip() or not self.canonical_name.strip():
            raise ValueError("pattern and canonical_name must contain usable text")
        if self.customer_id is not None and self.vendor_id is not None:
            raise ValueError("an alias cannot reference both a customer and vendor")
        if self.counterparty_role == "not_applicable" and (
            self.customer_id is not None or self.vendor_id is not None
        ):
            raise ValueError("not_applicable aliases cannot reference a contact")
        return self


class BankCounterpartyAliasResponse(BaseModel):
    id: int
    pattern: str
    normalized_pattern: str
    canonical_name: str
    bank_account_id: Optional[int]
    direction: str
    counterparty_role: str
    customer_id: Optional[int]
    vendor_id: Optional[int]
    default_account_id: Optional[int]
    default_class_id: Optional[int]
    is_active: bool
    normalizer_version: str
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BankTransactionPost(StrictModel):
    counter_account_id: int
    class_id: Optional[int] = None
    description: Optional[str] = None
    reference: Optional[str] = None


class BankTransferPost(StrictModel):
    first_transaction_id: int
    second_transaction_id: int
    description: Optional[str] = None
    reference: Optional[str] = None


class ReconciliationCreate(StrictModel):
    bank_account_id: int
    statement_date: dt_date
    statement_balance: Decimal


class ReconciliationResponse(BaseModel):
    id: int
    bank_account_id: int
    statement_date: dt_date
    statement_balance: Decimal
    status: ReconciliationStatus
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
