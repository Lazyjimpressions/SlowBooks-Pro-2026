from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, model_validator
from app.schemas.common import StrictModel
from app.schemas.banking import (
    BankProposalIntent,
    BankProposalRoute,
    ClassResolution,
    CounterpartyResolution,
    CounterpartyRole,
)


class BankRuleCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    pattern: str = Field(min_length=1, max_length=200)
    account_id: Optional[int] = None
    vendor_id: Optional[int] = None
    customer_id: Optional[int] = None
    bank_account_id: Optional[int] = None
    class_id: Optional[int] = None
    rule_type: str = Field(default="contains", pattern="^(contains|starts_with|exact)$")
    match_field: str = Field(default="raw", pattern="^(raw|normalized)$")
    direction: str = Field(default="any", pattern="^(any|deposit|withdrawal)$")
    minimum_amount: Optional[Decimal] = Field(default=None, ge=0)
    maximum_amount: Optional[Decimal] = Field(default=None, ge=0)
    intent: Optional[BankProposalIntent] = None
    posting_route: Optional[BankProposalRoute] = None
    counterparty_role: Optional[CounterpartyRole] = None
    counterparty_resolution: Optional[CounterpartyResolution] = None
    class_resolution: Optional[ClassResolution] = None
    priority: int = 0
    is_active: bool = True

    @model_validator(mode="after")
    def validate_rule(self):
        if not self.name.strip() or not self.pattern.strip():
            raise ValueError("name and pattern must contain usable text")
        if (
            self.minimum_amount is not None
            and self.maximum_amount is not None
            and self.minimum_amount > self.maximum_amount
        ):
            raise ValueError("minimum_amount cannot exceed maximum_amount")
        if self.customer_id is not None and self.vendor_id is not None:
            raise ValueError("a rule cannot reference both a customer and vendor")
        if self.counterparty_resolution == "customer" and self.customer_id is None:
            raise ValueError("customer resolution requires customer_id")
        if self.counterparty_resolution == "vendor" and self.vendor_id is None:
            raise ValueError("vendor resolution requires vendor_id")
        if self.customer_id is not None and self.counterparty_resolution != "customer":
            raise ValueError("customer_id requires customer resolution")
        if self.vendor_id is not None and self.counterparty_resolution != "vendor":
            raise ValueError("vendor_id requires vendor resolution")
        if self.class_resolution == "assigned" and self.class_id is None:
            raise ValueError("assigned class resolution requires class_id")
        if self.class_id is not None and self.class_resolution != "assigned":
            raise ValueError("class_id requires assigned class resolution")
        if self.counterparty_role == "not_applicable" and (
            self.counterparty_resolution != "not_applicable"
        ):
            raise ValueError("not-applicable role requires not-applicable resolution")
        if self.counterparty_resolution == "not_applicable" and (
            self.counterparty_role != "not_applicable"
        ):
            raise ValueError("not-applicable resolution requires not-applicable role")
        direction_by_intent = {
            "direct_expense": "withdrawal",
            "bill_payment": "withdrawal",
            "owner_draw": "withdrawal",
            "loan_payment": "withdrawal",
            "direct_income": "deposit",
            "customer_payment": "deposit",
            "owner_contribution": "deposit",
            "loan_proceeds": "deposit",
        }
        required_direction = direction_by_intent.get(self.intent)
        if required_direction and self.direction != required_direction:
            raise ValueError(f"{self.intent} requires {required_direction} direction")
        if (self.intent is None) != (self.posting_route is None):
            raise ValueError("intent and posting_route must be set together")
        allowed_routes = {
            "direct_expense": {"direct"},
            "direct_income": {"direct"},
            "customer_payment": {"customer_payment", "hold"},
            "bill_payment": {"bill_payment", "hold"},
            "transfer": {"hold"},
            "owner_contribution": {"direct", "hold"},
            "owner_draw": {"direct", "hold"},
            "loan_proceeds": {"direct", "hold"},
            "loan_payment": {"hold"},
            "investment_activity": {"hold"},
            "reimbursement": {"direct", "hold"},
            "unknown": {"hold"},
        }
        if self.intent and self.posting_route not in allowed_routes[self.intent]:
            raise ValueError(f"{self.posting_route} is invalid for {self.intent}")
        return self


class BankRuleUpdate(StrictModel):
    name: Optional[str] = None
    pattern: Optional[str] = None
    account_id: Optional[int] = None
    vendor_id: Optional[int] = None
    customer_id: Optional[int] = None
    bank_account_id: Optional[int] = None
    class_id: Optional[int] = None
    rule_type: Optional[str] = None
    match_field: Optional[str] = None
    direction: Optional[str] = None
    minimum_amount: Optional[Decimal] = None
    maximum_amount: Optional[Decimal] = None
    intent: Optional[BankProposalIntent] = None
    posting_route: Optional[BankProposalRoute] = None
    counterparty_role: Optional[CounterpartyRole] = None
    counterparty_resolution: Optional[CounterpartyResolution] = None
    class_resolution: Optional[ClassResolution] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class BankRuleResponse(BaseModel):
    id: int
    name: str
    pattern: str
    account_id: Optional[int]
    vendor_id: Optional[int]
    customer_id: Optional[int]
    bank_account_id: Optional[int]
    class_id: Optional[int]
    rule_type: str
    match_field: str
    direction: str
    minimum_amount: Optional[Decimal]
    maximum_amount: Optional[Decimal]
    intent: Optional[str]
    posting_route: Optional[str]
    counterparty_role: Optional[str]
    counterparty_resolution: Optional[str]
    class_resolution: Optional[str]
    priority: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
