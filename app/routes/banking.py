# ============================================================================
# Bank accounts + reconciliation — toggle cleared items, then validate
# their sum matches the statement balance.
# ============================================================================

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes._helpers import clamp_pagination
from app.models.accounts import Account
from app.models.banking import (
    BankAccount,
    BankCounterpartyAlias,
    BankTransaction,
    BankTransactionProposal,
    Reconciliation,
    ReconciliationStatus,
)
from app.models.bills import Bill
from app.models.classes import TxnClass
from app.models.contacts import Customer, Vendor
from app.models.invoices import Invoice
from app.schemas.banking import (
    BankAccountCreate,
    BankAccountUpdate,
    BankAccountResponse,
    BankTransactionCreate,
    BankTransactionResponse,
    BankTransactionPost,
    BankTransactionProposalCreate,
    BankTransactionProposalResponse,
    BankProposalReviewAction,
    BankProposalBulkApprove,
    BankReviewQueueItem,
    BankTransactionReviewResponse,
    BankCounterpartyAliasCreate,
    BankCounterpartyAliasResponse,
    BankTransferPost,
    ReconciliationCreate,
    ReconciliationResponse,
)
from app.services.closing_date import check_closing_date
from app.services.bank_posting import post_bank_transaction, post_bank_transfer
from app.services.bank_classification import build_bank_suggestion
from app.services.bank_normalization import (
    NORMALIZER_VERSION,
    normalize_bank_text,
    normalize_contact_name,
)

router = APIRouter(prefix="/api/banking", tags=["banking"])


# Bank Accounts
@router.get("/accounts", response_model=list[BankAccountResponse])
def list_bank_accounts(db: Session = Depends(get_db)):
    return (
        db.query(BankAccount)
        .filter(BankAccount.is_active)
        .order_by(BankAccount.name)
        .all()
    )


@router.get("/accounts/{account_id}", response_model=BankAccountResponse)
def get_bank_account(account_id: int, db: Session = Depends(get_db)):
    ba = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not ba:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return ba


@router.post("/accounts", response_model=BankAccountResponse, status_code=201)
def create_bank_account(data: BankAccountCreate, db: Session = Depends(get_db)):
    ba = BankAccount(**data.model_dump())
    db.add(ba)
    db.commit()
    db.refresh(ba)
    return ba


@router.put("/accounts/{account_id}", response_model=BankAccountResponse)
def update_bank_account(
    account_id: int, data: BankAccountUpdate, db: Session = Depends(get_db)
):
    ba = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not ba:
        raise HTTPException(status_code=404, detail="Bank account not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(ba, key, val)
    db.commit()
    db.refresh(ba)
    return ba


# Bank Transactions
@router.get("/transactions", response_model=list[BankTransactionResponse])
def list_bank_transactions(
    bank_account_id: int = None,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    skip, limit = clamp_pagination(skip, limit)
    q = db.query(BankTransaction)
    if bank_account_id:
        q = q.filter(BankTransaction.bank_account_id == bank_account_id)
    return q.order_by(BankTransaction.date.desc()).offset(skip).limit(limit).all()


@router.post("/transactions", response_model=BankTransactionResponse, status_code=201)
def create_bank_transaction(data: BankTransactionCreate, db: Session = Depends(get_db)):
    check_closing_date(db, data.date)
    ba = db.query(BankAccount).filter(BankAccount.id == data.bank_account_id).first()
    if not ba:
        raise HTTPException(status_code=404, detail="Bank account not found")

    txn = BankTransaction(**data.model_dump())
    ba.balance += data.amount
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


ACTIVE_PROPOSAL_STATUSES = ("proposed", "approved")
REVIEWABLE_PROPOSAL_STATUSES = ("proposed", "approved")
SAFE_BULK_INTENTS = ("direct_expense", "direct_income")
SAFE_BULK_MAX_ABS_AMOUNT = Decimal("1000.00")
REFERENCE_MODELS = {
    "customer_id": Customer,
    "vendor_id": Vendor,
    "counter_account_id": Account,
    "class_id": TxnClass,
    "invoice_id": Invoice,
    "bill_id": Bill,
    "paired_bank_transaction_id": BankTransaction,
}


def _active_proposal_query(db: Session):
    return db.query(BankTransactionProposal).filter(
        BankTransactionProposal.status.in_(ACTIVE_PROPOSAL_STATUSES)
    )


def _active_proposals_by_transaction(
    db: Session, transaction_ids: list[int]
) -> dict[int, BankTransactionProposal]:
    if not transaction_ids:
        return {}
    proposals = _active_proposal_query(db).filter(
        BankTransactionProposal.bank_transaction_id.in_(transaction_ids)
    )
    return {proposal.bank_transaction_id: proposal for proposal in proposals.all()}


def _validate_reference_ids(db: Session, values: dict) -> None:
    for field, model in REFERENCE_MODELS.items():
        object_id = values.get(field)
        if object_id is not None and db.get(model, object_id) is None:
            raise HTTPException(status_code=400, detail=f"Invalid {field}")


def _actor(db: Session) -> str:
    return db.info.get("acting_username") or "system"


def _proposal_values(data: BankTransactionProposalCreate) -> dict:
    values = data.model_dump()
    values["proposal_source"] = "human"
    if data.normalized_counterparty:
        values["normalized_counterparty"] = data.normalized_counterparty.strip()
        values["normalized_counterparty_key"] = normalize_contact_name(
            data.normalized_counterparty
        )
    else:
        values["normalized_counterparty"] = None
        values["normalized_counterparty_key"] = None
    return values


def _proposal_or_404(db: Session, proposal_id: int) -> BankTransactionProposal:
    proposal = db.get(BankTransactionProposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Bank proposal not found")
    return proposal


def _validate_proposal_for_approval(
    db: Session, proposal: BankTransactionProposal
) -> None:
    """Validate a complete review decision without posting accounting entries."""
    allowed_routes = {
        "direct_expense": {"direct"},
        "direct_income": {"direct"},
        "customer_payment": {"customer_payment"},
        "bill_payment": {"bill_payment"},
        "transfer": {"transfer"},
        "owner_contribution": {"direct"},
        "owner_draw": {"direct"},
        "loan_proceeds": {"direct"},
        "loan_payment": {"hold"},
        "investment_activity": {"hold"},
        "reimbursement": {"direct", "hold"},
    }
    if proposal.intent == "unknown":
        raise HTTPException(status_code=422, detail="Intent must be resolved")
    if proposal.posting_route not in allowed_routes.get(proposal.intent, set()):
        raise HTTPException(
            status_code=422,
            detail=f"{proposal.posting_route} is not valid for {proposal.intent}",
        )
    if proposal.counterparty_resolution == "unresolved":
        raise HTTPException(status_code=422, detail="Counterparty decision is required")
    if proposal.counterparty_role is None:
        raise HTTPException(status_code=422, detail="Counterparty role is required")
    if proposal.class_resolution == "unresolved":
        raise HTTPException(status_code=422, detail="Class decision is required")

    if proposal.class_resolution == "assigned":
        txn_class = db.get(TxnClass, proposal.class_id)
        if txn_class is None or txn_class.is_archived:
            raise HTTPException(status_code=422, detail="Assigned class must be active")

    if proposal.counterparty_resolution == "customer":
        customer = db.get(Customer, proposal.customer_id)
        if customer is None or not customer.is_active:
            raise HTTPException(
                status_code=422, detail="Assigned customer must be active"
            )
    elif proposal.counterparty_resolution == "vendor":
        vendor = db.get(Vendor, proposal.vendor_id)
        if vendor is None or not vendor.is_active:
            raise HTTPException(
                status_code=422, detail="Assigned vendor must be active"
            )

    if proposal.intent in SAFE_BULK_INTENTS:
        if proposal.class_resolution == "not_applicable":
            raise HTTPException(
                status_code=422,
                detail="Income and expense activity requires an assigned or personal/no-class decision",
            )
        expected_role = "payer" if proposal.intent == "direct_income" else "payee"
        if proposal.counterparty_role != expected_role:
            raise HTTPException(
                status_code=422,
                detail=f"{proposal.intent} requires counterparty role {expected_role}",
            )
        allowed_contacts = (
            {"customer", "text_only"}
            if proposal.intent == "direct_income"
            else {"vendor", "text_only"}
        )
        if proposal.counterparty_resolution not in allowed_contacts:
            raise HTTPException(
                status_code=422,
                detail=f"{proposal.intent} has an incompatible counterparty decision",
            )

    if proposal.posting_route == "direct":
        account = db.get(Account, proposal.counter_account_id)
        if account is None or not account.is_active:
            raise HTTPException(
                status_code=422,
                detail="Direct proposals require an active counter-account",
            )
    elif proposal.posting_route == "transfer":
        if proposal.paired_bank_transaction_id is None:
            raise HTTPException(
                status_code=422, detail="Transfers require a paired bank transaction"
            )
        if (
            proposal.counterparty_resolution != "not_applicable"
            or proposal.counterparty_role != "not_applicable"
            or proposal.class_resolution != "not_applicable"
        ):
            raise HTTPException(
                status_code=422,
                detail="Transfers require contact and class to be not applicable",
            )
    elif proposal.posting_route == "customer_payment":
        if (
            proposal.counterparty_resolution != "customer"
            or proposal.counterparty_role != "payer"
        ):
            raise HTTPException(
                status_code=422,
                detail="Customer payments require an existing customer as payer",
            )
    elif proposal.posting_route == "bill_payment":
        if (
            proposal.counterparty_resolution != "vendor"
            or proposal.counterparty_role != "payee"
        ):
            raise HTTPException(
                status_code=422,
                detail="Bill payments require an existing vendor as payee",
            )


def _approve_proposal(db: Session, proposal: BankTransactionProposal) -> None:
    if proposal.status == "approved":
        return
    if proposal.status != "proposed":
        raise HTTPException(
            status_code=409, detail="Only proposed items can be approved"
        )
    if proposal.bank_transaction.transaction_id is not None:
        raise HTTPException(
            status_code=409, detail="Bank transaction is already posted"
        )
    _validate_proposal_for_approval(db, proposal)
    proposal.status = "approved"
    proposal.reviewed_by = _actor(db)
    proposal.reviewed_at = datetime.now().astimezone()


def _bulk_fingerprint(proposal: BankTransactionProposal) -> tuple:
    txn = proposal.bank_transaction
    return (
        proposal.intent,
        proposal.posting_route,
        proposal.normalized_counterparty_key,
        proposal.counterparty_role,
        proposal.counterparty_resolution,
        proposal.customer_id,
        proposal.vendor_id,
        proposal.counter_account_id,
        proposal.class_resolution,
        proposal.class_id,
        abs(Decimal(str(txn.amount))),
    )


def _persist_proposal(
    db: Session, transaction_id: int, values: dict
) -> BankTransactionProposal:
    txn = db.get(BankTransaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")
    if txn.transaction_id is not None:
        raise HTTPException(
            status_code=409, detail="Bank transaction is already posted"
        )
    if (
        _active_proposal_query(db)
        .filter(BankTransactionProposal.bank_transaction_id == transaction_id)
        .first()
    ):
        raise HTTPException(
            status_code=409,
            detail="Bank transaction already has an active proposal",
        )

    _validate_reference_ids(db, values)
    if values.get("paired_bank_transaction_id") == transaction_id:
        raise HTTPException(
            status_code=400, detail="A bank transaction cannot be paired with itself"
        )

    revision = (
        db.query(func.max(BankTransactionProposal.revision))
        .filter(BankTransactionProposal.bank_transaction_id == transaction_id)
        .scalar()
        or 0
    ) + 1
    proposal = BankTransactionProposal(
        bank_transaction_id=transaction_id,
        revision=revision,
        status="proposed",
        created_by=db.info.get("acting_username") or "system",
        **values,
    )
    db.add(proposal)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A concurrent proposal already became active; reload and retry",
        )
    db.refresh(proposal)
    return proposal


@router.get("/review", response_model=list[BankReviewQueueItem])
def list_bank_review_queue(
    status: str = Query(
        "unresolved",
        pattern="^(unresolved|proposed|approved|posted|all)$",
    ),
    bank_account_id: int = None,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    """List imported rows by review state without changing import behavior."""
    skip, limit = clamp_pagination(skip, limit)
    q = db.query(BankTransaction)
    if bank_account_id:
        q = q.filter(BankTransaction.bank_account_id == bank_account_id)

    if status == "unresolved":
        active_exists = (
            db.query(BankTransactionProposal.id)
            .filter(
                BankTransactionProposal.bank_transaction_id == BankTransaction.id,
                BankTransactionProposal.status.in_(ACTIVE_PROPOSAL_STATUSES),
            )
            .exists()
        )
        q = q.filter(BankTransaction.transaction_id.is_(None), ~active_exists)
    elif status in ACTIVE_PROPOSAL_STATUSES:
        q = q.join(
            BankTransactionProposal,
            BankTransactionProposal.bank_transaction_id == BankTransaction.id,
        ).filter(BankTransactionProposal.status == status)
    elif status == "posted":
        q = q.filter(BankTransaction.transaction_id.is_not(None))

    rows = (
        q.order_by(BankTransaction.date.desc(), BankTransaction.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    active_by_transaction = _active_proposals_by_transaction(
        db, [txn.id for txn in rows]
    )
    return [
        {
            "transaction": txn,
            "active_proposal": active_by_transaction.get(txn.id),
        }
        for txn in rows
    ]


@router.get(
    "/transactions/{transaction_id}/review",
    response_model=BankTransactionReviewResponse,
)
def get_bank_transaction_review(transaction_id: int, db: Session = Depends(get_db)):
    txn = db.get(BankTransaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")
    item = {
        "transaction": txn,
        "active_proposal": _active_proposals_by_transaction(db, [txn.id]).get(txn.id),
    }
    item["proposal_history"] = (
        db.query(BankTransactionProposal)
        .filter(BankTransactionProposal.bank_transaction_id == transaction_id)
        .order_by(BankTransactionProposal.revision.desc())
        .all()
    )
    return item


@router.post(
    "/transactions/{transaction_id}/proposals",
    response_model=BankTransactionProposalResponse,
    status_code=201,
)
def create_bank_transaction_proposal(
    transaction_id: int,
    data: BankTransactionProposalCreate,
    db: Session = Depends(get_db),
):
    """Create a review proposal. This endpoint never posts to the ledger."""
    return _persist_proposal(db, transaction_id, _proposal_values(data))


@router.post(
    "/transactions/{transaction_id}/suggest",
    response_model=BankTransactionProposalResponse,
    status_code=201,
)
def suggest_bank_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Create one deterministic proposal without posting or changing evidence."""
    txn = db.get(BankTransaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")
    return _persist_proposal(db, transaction_id, build_bank_suggestion(db, txn))


@router.put(
    "/proposals/{proposal_id}",
    response_model=BankTransactionProposalResponse,
    status_code=201,
)
def correct_bank_proposal(
    proposal_id: int,
    data: BankTransactionProposalCreate,
    db: Session = Depends(get_db),
):
    """Create a human-reviewed revision; imported evidence remains untouched."""
    current = _proposal_or_404(db, proposal_id)
    if current.status not in REVIEWABLE_PROPOSAL_STATUSES:
        raise HTTPException(
            status_code=409, detail="Only proposed or approved items can be corrected"
        )
    if current.bank_transaction.transaction_id is not None:
        raise HTTPException(
            status_code=409, detail="Bank transaction is already posted"
        )
    values = _proposal_values(data)
    _validate_reference_ids(db, values)
    if values.get("paired_bank_transaction_id") == current.bank_transaction_id:
        raise HTTPException(
            status_code=400, detail="A bank transaction cannot be paired with itself"
        )
    revision = (
        db.query(func.max(BankTransactionProposal.revision))
        .filter(
            BankTransactionProposal.bank_transaction_id == current.bank_transaction_id
        )
        .scalar()
        or 0
    ) + 1
    now = datetime.now().astimezone()
    current.status = "superseded"
    current.reviewed_by = _actor(db)
    current.reviewed_at = now
    db.flush()
    replacement = BankTransactionProposal(
        bank_transaction_id=current.bank_transaction_id,
        revision=revision,
        status="proposed",
        supersedes_id=current.id,
        created_by=_actor(db),
        **values,
    )
    db.add(replacement)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A concurrent review changed this proposal; reload and retry",
        )
    db.refresh(replacement)
    return replacement


@router.post(
    "/proposals/bulk-approve",
    response_model=list[BankTransactionProposalResponse],
)
def bulk_approve_bank_proposals(
    data: BankProposalBulkApprove, db: Session = Depends(get_db)
):
    proposals = (
        db.query(BankTransactionProposal)
        .filter(BankTransactionProposal.id.in_(data.proposal_ids))
        .all()
    )
    if len(proposals) != len(data.proposal_ids):
        raise HTTPException(
            status_code=404, detail="One or more proposals were not found"
        )
    for proposal in proposals:
        _validate_proposal_for_approval(db, proposal)
        if proposal.status != "proposed" or proposal.intent not in SAFE_BULK_INTENTS:
            raise HTTPException(
                status_code=422,
                detail="Bulk approval is limited to proposed direct income or expense items",
            )
        if (
            abs(Decimal(str(proposal.bank_transaction.amount)))
            > SAFE_BULK_MAX_ABS_AMOUNT
        ):
            raise HTTPException(
                status_code=422,
                detail="Amounts above $1,000 require individual approval",
            )
    if len({_bulk_fingerprint(proposal) for proposal in proposals}) != 1:
        raise HTTPException(
            status_code=422,
            detail="Bulk approval requires identical counterparty, amount, account, and class decisions",
        )
    for proposal in proposals:
        _approve_proposal(db, proposal)
    db.commit()
    return sorted(proposals, key=lambda proposal: data.proposal_ids.index(proposal.id))


@router.post(
    "/proposals/{proposal_id}/approve",
    response_model=BankTransactionProposalResponse,
)
def approve_bank_proposal(proposal_id: int, db: Session = Depends(get_db)):
    proposal = _proposal_or_404(db, proposal_id)
    _approve_proposal(db, proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


@router.post(
    "/proposals/{proposal_id}/reject",
    response_model=BankTransactionProposalResponse,
)
def reject_bank_proposal(
    proposal_id: int,
    data: BankProposalReviewAction,
    db: Session = Depends(get_db),
):
    proposal = _proposal_or_404(db, proposal_id)
    if proposal.status == "rejected":
        return proposal
    if proposal.status != "proposed":
        raise HTTPException(
            status_code=409, detail="Only proposed items can be rejected"
        )
    proposal.status = "rejected"
    proposal.review_note = data.note.strip() if data.note else None
    proposal.reviewed_by = _actor(db)
    proposal.reviewed_at = datetime.now().astimezone()
    db.commit()
    db.refresh(proposal)
    return proposal


@router.post(
    "/proposals/{proposal_id}/supersede",
    response_model=BankTransactionProposalResponse,
)
def supersede_bank_proposal(
    proposal_id: int,
    data: BankProposalReviewAction,
    db: Session = Depends(get_db),
):
    proposal = _proposal_or_404(db, proposal_id)
    if proposal.status == "superseded":
        return proposal
    if proposal.status not in REVIEWABLE_PROPOSAL_STATUSES:
        raise HTTPException(
            status_code=409, detail="Only proposed or approved items can be superseded"
        )
    if proposal.bank_transaction.transaction_id is not None:
        raise HTTPException(status_code=409, detail="Posted work must be reversed")
    proposal.status = "superseded"
    proposal.review_note = data.note.strip() if data.note else None
    proposal.reviewed_by = _actor(db)
    proposal.reviewed_at = datetime.now().astimezone()
    db.commit()
    db.refresh(proposal)
    return proposal


@router.get("/counterparty-aliases", response_model=list[BankCounterpartyAliasResponse])
def list_counterparty_aliases(
    bank_account_id: int = None, db: Session = Depends(get_db)
):
    query = db.query(BankCounterpartyAlias).filter(BankCounterpartyAlias.is_active)
    if bank_account_id is not None:
        query = query.filter(
            (BankCounterpartyAlias.bank_account_id == bank_account_id)
            | BankCounterpartyAlias.bank_account_id.is_(None)
        )
    return query.order_by(
        BankCounterpartyAlias.bank_account_id.desc(),
        BankCounterpartyAlias.canonical_name,
    ).all()


@router.post(
    "/counterparty-aliases",
    response_model=BankCounterpartyAliasResponse,
    status_code=201,
)
def create_counterparty_alias(
    data: BankCounterpartyAliasCreate, db: Session = Depends(get_db)
):
    values = data.model_dump()
    if data.bank_account_id is not None:
        scoped_register = db.get(BankAccount, data.bank_account_id)
        if scoped_register is None:
            raise HTTPException(status_code=400, detail="Invalid bank_account_id")
        if not scoped_register.is_active:
            raise HTTPException(status_code=400, detail="Inactive bank_account_id")
    for field, model in (
        ("customer_id", Customer),
        ("vendor_id", Vendor),
        ("default_account_id", Account),
        ("default_class_id", TxnClass),
    ):
        object_id = values.get(field)
        if object_id is None:
            continue
        referenced = db.get(model, object_id)
        if referenced is None:
            raise HTTPException(status_code=400, detail=f"Invalid {field}")
        if field in ("customer_id", "vendor_id", "default_account_id") and not (
            referenced.is_active
        ):
            raise HTTPException(status_code=400, detail=f"Inactive {field}")
        if field == "default_class_id" and referenced.is_archived:
            raise HTTPException(status_code=400, detail="Archived default_class_id")

    normalized = normalize_bank_text(data.pattern, None)
    if not normalized.normalized_key:
        raise HTTPException(status_code=400, detail="Alias pattern has no usable text")
    values.update(
        pattern=data.pattern.strip(),
        canonical_name=data.canonical_name.strip(),
        normalized_pattern=normalized.normalized_key,
        normalizer_version=NORMALIZER_VERSION,
        created_by=db.info.get("acting_username") or "system",
    )
    alias = BankCounterpartyAlias(**values)
    db.add(alias)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An active alias already exists for this scope and direction",
        )
    db.refresh(alias)
    return alias


@router.delete("/counterparty-aliases/{alias_id}")
def deactivate_counterparty_alias(alias_id: int, db: Session = Depends(get_db)):
    alias = db.get(BankCounterpartyAlias, alias_id)
    if not alias:
        raise HTTPException(status_code=404, detail="Counterparty alias not found")
    alias.is_active = False
    db.commit()
    return {"status": "deactivated", "id": alias_id}


@router.post("/transactions/{transaction_id}/post")
def post_transaction(
    transaction_id: int,
    data: BankTransactionPost,
    db: Session = Depends(get_db),
):
    feed_row = db.get(BankTransaction, transaction_id)
    if not feed_row:
        raise HTTPException(status_code=404, detail="Bank transaction not found")
    try:
        return post_bank_transaction(
            db,
            feed_row,
            data.counter_account_id,
            class_id=data.class_id,
            description=data.description,
            reference=data.reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/transfers/post")
def post_transfer(data: BankTransferPost, db: Session = Depends(get_db)):
    first = db.get(BankTransaction, data.first_transaction_id)
    second = db.get(BankTransaction, data.second_transaction_id)
    if not first or not second:
        raise HTTPException(status_code=404, detail="Bank transaction not found")
    try:
        return post_bank_transfer(
            db,
            first,
            second,
            description=data.description,
            reference=data.reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Reconciliations
@router.get("/reconciliations", response_model=list[ReconciliationResponse])
def list_reconciliations(bank_account_id: int = None, db: Session = Depends(get_db)):
    q = db.query(Reconciliation)
    if bank_account_id:
        q = q.filter(Reconciliation.bank_account_id == bank_account_id)
    return q.order_by(Reconciliation.statement_date.desc()).all()


@router.post("/reconciliations", response_model=ReconciliationResponse, status_code=201)
def create_reconciliation(data: ReconciliationCreate, db: Session = Depends(get_db)):
    """Start a reconciliation."""
    ba = db.query(BankAccount).filter(BankAccount.id == data.bank_account_id).first()
    if not ba:
        raise HTTPException(status_code=404, detail="Bank account not found")
    recon = Reconciliation(**data.model_dump())
    db.add(recon)
    db.commit()
    db.refresh(recon)
    return recon


@router.get("/reconciliations/{recon_id}/transactions")
def get_reconciliation_transactions(recon_id: int, db: Session = Depends(get_db)):
    """Get unreconciled transactions for this bank account"""
    recon = db.query(Reconciliation).filter(Reconciliation.id == recon_id).first()
    if not recon:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    txns = (
        db.query(BankTransaction)
        .filter(BankTransaction.bank_account_id == recon.bank_account_id)
        .filter(BankTransaction.date <= recon.statement_date)
        .order_by(BankTransaction.date)
        .all()
    )

    # Sum and subtract in Decimal so a reconciliation that's actually zero
    # doesn't show $0.00000001 of "difference" from float drift over hundreds
    # of cleared transactions. Convert to float only at the JSON boundary.
    cleared_total = sum(
        (Decimal(str(t.amount)) for t in txns if t.reconciled), Decimal("0")
    )
    uncleared_total = sum(
        (Decimal(str(t.amount)) for t in txns if not t.reconciled), Decimal("0")
    )
    statement_bal = Decimal(str(recon.statement_balance or 0))
    difference = statement_bal - cleared_total

    return {
        "reconciliation_id": recon.id,
        "statement_balance": float(statement_bal),
        "cleared_total": float(cleared_total),
        "uncleared_total": float(uncleared_total),
        "difference": float(difference),
        "transactions": [
            {
                "id": t.id,
                "date": t.date.isoformat(),
                "payee": t.payee or "",
                "description": t.description or "",
                "amount": float(t.amount),
                "check_number": t.check_number,
                "reconciled": t.reconciled,
            }
            for t in txns
        ],
    }


@router.post("/reconciliations/{recon_id}/toggle/{txn_id}")
def toggle_cleared(recon_id: int, txn_id: int, db: Session = Depends(get_db)):
    """Toggle a transaction's cleared status."""
    recon = db.query(Reconciliation).filter(Reconciliation.id == recon_id).first()
    if not recon:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    if recon.status == ReconciliationStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Reconciliation already completed")

    txn = db.query(BankTransaction).filter(BankTransaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    txn.reconciled = not txn.reconciled
    db.commit()
    return {"id": txn.id, "reconciled": txn.reconciled}


@router.get("/check-register")
def check_register(account_id: int = None, db: Session = Depends(get_db)):
    """Check register — filtered view of transactions for a bank account."""
    from app.models.transactions import Transaction, TransactionLine
    from app.models.accounts import Account

    if not account_id:
        # Default to first bank account (checking - 1000)
        acct = db.query(Account).filter(Account.account_number == "1000").first()
        if acct:
            account_id = acct.id
        else:
            return {"account_id": None, "account_name": "", "entries": []}

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    lines = (
        db.query(TransactionLine, Transaction)
        .join(Transaction, TransactionLine.transaction_id == Transaction.id)
        .filter(TransactionLine.account_id == account_id)
        .order_by(Transaction.date, Transaction.id)
        .all()
    )

    entries = []
    running_balance = Decimal("0")
    for tl, txn in lines:
        # For asset accounts: debits increase, credits decrease
        if account.account_type.value in ("asset", "expense", "cogs"):
            running_balance += tl.debit - tl.credit
        else:
            running_balance += tl.credit - tl.debit

        entries.append(
            {
                "date": txn.date.isoformat(),
                "description": txn.description or tl.description or "",
                "reference": txn.reference or "",
                "source_type": txn.source_type or "",
                "payment": float(tl.credit) if tl.credit > 0 else 0,
                "deposit": float(tl.debit) if tl.debit > 0 else 0,
                "balance": float(running_balance),
            }
        )

    return {
        "account_id": account_id,
        "account_name": account.name,
        "account_number": account.account_number,
        "entries": entries,
    }


@router.post("/reconciliations/{recon_id}/complete")
def complete_reconciliation(recon_id: int, db: Session = Depends(get_db)):
    """Finish a reconciliation — validates the difference is 0."""
    recon = db.query(Reconciliation).filter(Reconciliation.id == recon_id).first()
    if not recon:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    if recon.status == ReconciliationStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Already completed")

    txns = (
        db.query(BankTransaction)
        .filter(BankTransaction.bank_account_id == recon.bank_account_id)
        .filter(BankTransaction.date <= recon.statement_date)
        .filter(BankTransaction.reconciled)
        .all()
    )
    cleared_total = sum(t.amount for t in txns)

    if abs(cleared_total - recon.statement_balance) > Decimal("0.01"):
        raise HTTPException(
            status_code=400,
            detail=f"Difference is ${float(recon.statement_balance - cleared_total):.2f} — must be $0.00 to complete",
        )

    recon.status = ReconciliationStatus.COMPLETED
    recon.completed_at = datetime.utcnow()
    db.commit()
    return {"status": "completed", "reconciliation_id": recon.id}
