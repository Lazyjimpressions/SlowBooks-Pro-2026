# ============================================================================
# Bank Rules — auto-categorize imported bank transactions
# Phase 10: Quick Wins + Medium Effort Features
# ============================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.accounts import Account
from app.models.bank_rules import BankRule
from app.models.banking import BankAccount, BankTransactionProposal
from app.models.classes import TxnClass
from app.models.contacts import Customer, Vendor
from app.schemas.bank_rules import BankRuleCreate, BankRuleUpdate, BankRuleResponse
from app.services.bank_rules_engine import apply_rules_to_scope

router = APIRouter(prefix="/api/bank-rules", tags=["bank-rules"])

REFERENCE_MODELS = {
    "account_id": Account,
    "vendor_id": Vendor,
    "customer_id": Customer,
    "bank_account_id": BankAccount,
    "class_id": TxnClass,
}


def _validated_values(db: Session, data: BankRuleCreate) -> dict:
    values = data.model_dump()
    values["name"] = data.name.strip()
    values["pattern"] = data.pattern.strip()
    for field, model in REFERENCE_MODELS.items():
        object_id = values.get(field)
        if object_id is None:
            continue
        referenced = db.get(model, object_id)
        if referenced is None:
            raise HTTPException(status_code=400, detail=f"Invalid {field}")
        if hasattr(referenced, "is_active") and not referenced.is_active:
            raise HTTPException(status_code=400, detail=f"Inactive {field}")
        if field == "class_id" and referenced.is_archived:
            raise HTTPException(status_code=400, detail="Archived class_id")
    return values


@router.get("", response_model=list[BankRuleResponse])
def list_rules(db: Session = Depends(get_db)):
    return db.query(BankRule).order_by(BankRule.priority.desc(), BankRule.name).all()


@router.get("/proposal-draft/{proposal_id}", response_model=BankRuleCreate)
def proposal_rule_draft(proposal_id: int, db: Session = Depends(get_db)):
    """Offer a narrow rule draft; this endpoint never creates a rule."""
    proposal = db.get(BankTransactionProposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Bank proposal not found")
    if proposal.status not in ("approved", "posted"):
        raise HTTPException(status_code=409, detail="Approve the proposal first")
    if proposal.intent not in ("direct_expense", "direct_income"):
        raise HTTPException(
            status_code=409,
            detail="Initial rule drafts are limited to direct income and expense",
        )
    row = proposal.bank_transaction
    pattern = (
        proposal.normalized_counterparty_key
        or proposal.normalized_counterparty
        or row.payee
        or row.description
    )
    if not pattern:
        raise HTTPException(status_code=409, detail="No usable matching text")
    direction = "deposit" if row.amount > 0 else "withdrawal"
    display = proposal.normalized_counterparty or pattern
    return BankRuleCreate(
        name=f"{display} - {direction}"[:200],
        pattern=pattern[:200],
        account_id=proposal.counter_account_id,
        vendor_id=proposal.vendor_id,
        customer_id=proposal.customer_id,
        bank_account_id=row.bank_account_id,
        class_id=proposal.class_id,
        rule_type="exact",
        match_field=("normalized" if proposal.normalized_counterparty_key else "raw"),
        direction=direction,
        intent=proposal.intent,
        posting_route=proposal.posting_route,
        counterparty_role=proposal.counterparty_role,
        counterparty_resolution=proposal.counterparty_resolution,
        class_resolution=proposal.class_resolution,
        priority=100,
    )


@router.get("/{rule_id}", response_model=BankRuleResponse)
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(BankRule).filter(BankRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.post("", response_model=BankRuleResponse, status_code=201)
def create_rule(data: BankRuleCreate, db: Session = Depends(get_db)):
    rule = BankRule(**_validated_values(db, data))
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=BankRuleResponse)
def update_rule(rule_id: int, data: BankRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(BankRule).filter(BankRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    current = {field: getattr(rule, field) for field in BankRuleCreate.model_fields}
    merged = BankRuleCreate(**{**current, **data.model_dump(exclude_unset=True)})
    for key, val in _validated_values(db, merged).items():
        setattr(rule, key, val)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(BankRule).filter(BankRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"status": "deleted"}


@router.post("/apply")
def apply_rules(db: Session = Depends(get_db)):
    """Create review proposals and legacy category hints; never post."""
    return apply_rules_to_scope(db)
