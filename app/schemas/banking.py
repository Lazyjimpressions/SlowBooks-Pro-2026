from datetime import date as dt_date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, model_validator
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
ClassResolution = Literal["unresolved", "personal_no_class", "assigned"]
ProposalSource = Literal["human", "rule", "deterministic", "ai"]


class BankTransactionProposalCreate(StrictModel):
    intent: BankProposalIntent = "unknown"
    posting_route: BankProposalRoute = "hold"
    normalized_counterparty: Optional[str] = None
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
    normalizer_version: Optional[str] = None

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
    rationale: Optional[str]
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
