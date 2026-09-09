"""Post and reverse approved bank proposals through guarded ledger services."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.accounts import Account, AccountType
from app.models.banking import BankAccount, BankTransaction, BankTransactionProposal
from app.models.transactions import (
    Transaction,
    TransactionCounterparty,
)
from app.services.accounting import create_journal_entry, reversing_lines
from app.services.bank_posting import post_bank_transaction, post_bank_transfer

DIRECT_SOURCE_TYPES = {
    "direct_expense": "bank_expense",
    "direct_income": "bank_income",
    "owner_contribution": "bank_activity",
    "owner_draw": "bank_activity",
    "loan_proceeds": "bank_activity",
    "reimbursement": "bank_activity",
}


def _result(status: str, proposals: list[BankTransactionProposal], txn_id: int):
    return {
        "status": status,
        "proposal_ids": [proposal.id for proposal in proposals],
        "transaction_id": txn_id,
        "bank_transaction_ids": [
            proposal.bank_transaction_id for proposal in proposals
        ],
        "replacement_proposal_ids": [],
    }


def _linked_account(db: Session, row: BankTransaction) -> Account:
    register = db.get(BankAccount, row.bank_account_id)
    account = db.get(Account, register.account_id) if register else None
    if account is None or not account.is_active:
        raise ValueError("The bank register must link to an active chart account")
    return account


def _validate_direct(proposal: BankTransactionProposal, counter: Account) -> None:
    amount = Decimal(str(proposal.bank_transaction.amount))
    if proposal.intent == "direct_expense":
        if amount >= 0 or counter.account_type not in (
            AccountType.EXPENSE,
            AccountType.COGS,
        ):
            raise ValueError("Direct expense requires a withdrawal and expense account")
    elif proposal.intent == "direct_income":
        if amount <= 0 or counter.account_type != AccountType.INCOME:
            raise ValueError("Direct income requires a deposit and income account")
    elif proposal.intent in ("owner_contribution", "owner_draw"):
        if counter.account_type != AccountType.EQUITY:
            raise ValueError("Owner activity requires an equity counter-account")
        if proposal.intent == "owner_contribution" and amount <= 0:
            raise ValueError("Owner contribution requires a deposit")
        if proposal.intent == "owner_draw" and amount >= 0:
            raise ValueError("Owner draw requires a withdrawal")
    elif proposal.intent == "loan_proceeds":
        if amount <= 0 or counter.account_type != AccountType.LIABILITY:
            raise ValueError("Loan proceeds require a deposit and liability account")
    elif proposal.intent == "reimbursement":
        if counter.account_type not in (AccountType.ASSET, AccountType.LIABILITY):
            raise ValueError(
                "Reimbursement direct posting requires a receivable or payable account"
            )


def _add_counterparty(
    db: Session, proposal: BankTransactionProposal, transaction_id: int
) -> None:
    if proposal.counterparty_role == "not_applicable":
        return
    row = proposal.bank_transaction
    display_name = (
        proposal.normalized_counterparty
        or row.payee
        or row.description
        or "Reviewed bank counterparty"
    )
    db.add(
        TransactionCounterparty(
            transaction_id=transaction_id,
            role=proposal.counterparty_role,
            display_name=display_name[:200],
            customer_id=proposal.customer_id,
            vendor_id=proposal.vendor_id,
            proposal_id=proposal.id,
        )
    )


def _mark_posted(
    proposals: list[BankTransactionProposal], transaction_id: int, now: datetime
) -> None:
    for proposal in proposals:
        proposal.status = "posted"
        proposal.posted_transaction_id = transaction_id
        proposal.posted_at = now


def _posted_group(db: Session, transaction_id: int) -> list[BankTransactionProposal]:
    return (
        db.query(BankTransactionProposal)
        .filter(
            BankTransactionProposal.posted_transaction_id == transaction_id,
            BankTransactionProposal.status == "posted",
        )
        .order_by(BankTransactionProposal.id)
        .all()
    )


def post_approved_proposal(db: Session, proposal_id: int) -> dict:
    """Post one approved proposal, atomically retaining its provenance."""
    proposal = (
        db.query(BankTransactionProposal)
        .filter(BankTransactionProposal.id == proposal_id)
        .with_for_update()
        .first()
    )
    if proposal is None:
        raise LookupError("Bank proposal not found")
    if proposal.status == "posted" and proposal.posted_transaction_id:
        return _result(
            "already_posted",
            _posted_group(db, proposal.posted_transaction_id),
            proposal.posted_transaction_id,
        )
    if proposal.status != "approved":
        raise ValueError("Only an approved proposal can post")
    if proposal.posting_route in ("customer_payment", "bill_payment", "hold"):
        raise ValueError(
            "This proposal is held for its domain workflow and cannot post generically"
        )

    row = (
        db.query(BankTransaction)
        .filter(BankTransaction.id == proposal.bank_transaction_id)
        .with_for_update()
        .first()
    )
    if row.transaction_id is not None:
        raise ValueError("Bank transaction is already linked to a ledger posting")

    proposals = [proposal]
    if proposal.posting_route == "transfer":
        pair = (
            db.query(BankTransactionProposal)
            .filter(
                BankTransactionProposal.bank_transaction_id
                == proposal.paired_bank_transaction_id,
                BankTransactionProposal.status == "approved",
            )
            .with_for_update()
            .first()
        )
        if (
            pair is None
            or pair.intent != "transfer"
            or pair.posting_route != "transfer"
            or pair.paired_bank_transaction_id != proposal.bank_transaction_id
        ):
            raise ValueError("Transfer requires a mutually paired approved proposal")
        proposals.append(pair)
        pair_row = (
            db.query(BankTransaction)
            .filter(BankTransaction.id == pair.bank_transaction_id)
            .with_for_update()
            .first()
        )
        if pair_row.transaction_id is not None:
            raise ValueError("Paired bank transaction is already posted")
        canonical_id = min(item.id for item in proposals)
        posted = post_bank_transfer(
            db,
            row,
            pair_row,
            description=proposal.rationale or None,
            reference=row.import_id or "",
            source_type="bank_proposal_transfer",
            source_id=canonical_id,
            commit=False,
        )
    else:
        if proposal.intent not in DIRECT_SOURCE_TYPES:
            raise ValueError("This approved intent has no guarded posting route")
        counter = db.get(Account, proposal.counter_account_id)
        if counter is None or not counter.is_active:
            raise ValueError("Approved counter-account is unavailable")
        _linked_account(db, row)
        _validate_direct(proposal, counter)
        if (
            proposal.intent not in ("direct_expense", "direct_income")
            and proposal.class_resolution != "not_applicable"
        ):
            raise ValueError(
                "Pure balance-sheet activity requires class to be not applicable"
            )
        class_id = (
            proposal.class_id if proposal.class_resolution == "assigned" else None
        )
        posted = post_bank_transaction(
            db,
            row,
            counter.id,
            class_id=class_id,
            description=proposal.normalized_counterparty
            or row.description
            or row.payee,
            reference=row.check_number or row.import_id or "",
            source_type=DIRECT_SOURCE_TYPES[proposal.intent],
            source_id=proposal.id,
            commit=False,
        )
        _add_counterparty(db, proposal, posted["transaction_id"])

    now = datetime.now().astimezone()
    _mark_posted(proposals, posted["transaction_id"], now)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        refreshed = db.get(BankTransactionProposal, proposal_id)
        if (
            refreshed
            and refreshed.status == "posted"
            and refreshed.posted_transaction_id
        ):
            return _result(
                "already_posted",
                _posted_group(db, refreshed.posted_transaction_id),
                refreshed.posted_transaction_id,
            )
        raise
    return _result("posted", proposals, posted["transaction_id"])


def _replacement_values(proposal: BankTransactionProposal, actor: str) -> dict:
    return {
        "bank_transaction_id": proposal.bank_transaction_id,
        "revision": proposal.revision + 1,
        "status": "proposed",
        "intent": proposal.intent,
        "posting_route": proposal.posting_route,
        "normalized_counterparty": proposal.normalized_counterparty,
        "normalized_counterparty_key": proposal.normalized_counterparty_key,
        "counterparty_role": proposal.counterparty_role,
        "counterparty_resolution": proposal.counterparty_resolution,
        "customer_id": proposal.customer_id,
        "vendor_id": proposal.vendor_id,
        "counter_account_id": proposal.counter_account_id,
        "class_resolution": proposal.class_resolution,
        "class_id": proposal.class_id,
        "invoice_id": proposal.invoice_id,
        "bill_id": proposal.bill_id,
        "paired_bank_transaction_id": proposal.paired_bank_transaction_id,
        "proposal_source": "human",
        "confidence": None,
        "confidence_components": None,
        "rationale": "Reopened after reversing the prior posting",
        "normalizer_version": proposal.normalizer_version,
        "supersedes_id": proposal.id,
        "created_by": actor,
    }


def reverse_posted_proposal(
    db: Session,
    proposal_id: int,
    *,
    reversal_date: date,
    actor: str,
    note: str | None = None,
) -> dict:
    """Reverse a proposal posting and create reviewable replacement revisions."""
    proposal = (
        db.query(BankTransactionProposal)
        .filter(BankTransactionProposal.id == proposal_id)
        .with_for_update()
        .first()
    )
    if proposal is None:
        raise LookupError("Bank proposal not found")
    if proposal.status == "reversed" and proposal.reversal_transaction_id:
        reversed_proposals = (
            db.query(BankTransactionProposal)
            .filter(
                BankTransactionProposal.reversal_transaction_id
                == proposal.reversal_transaction_id,
                BankTransactionProposal.status == "reversed",
            )
            .order_by(BankTransactionProposal.id)
            .all()
        )
        replacements = (
            db.query(BankTransactionProposal)
            .filter(
                BankTransactionProposal.supersedes_id.in_(
                    [item.id for item in reversed_proposals]
                )
            )
            .order_by(BankTransactionProposal.id)
            .all()
        )
        result = _result(
            "already_reversed", reversed_proposals, proposal.reversal_transaction_id
        )
        result["replacement_proposal_ids"] = [item.id for item in replacements]
        return result
    if proposal.status != "posted" or proposal.posted_transaction_id is None:
        raise ValueError("Only a posted proposal can be reversed")

    original = db.get(Transaction, proposal.posted_transaction_id)
    if original is None:
        raise ValueError("The proposal's posted journal entry is missing")
    proposals = (
        db.query(BankTransactionProposal)
        .filter(
            BankTransactionProposal.posted_transaction_id == original.id,
            BankTransactionProposal.status == "posted",
        )
        .with_for_update()
        .all()
    )
    rows = []
    for item in proposals:
        row = (
            db.query(BankTransaction)
            .filter(BankTransaction.id == item.bank_transaction_id)
            .with_for_update()
            .first()
        )
        if row.reconciled:
            raise ValueError("Reconciled bank transactions cannot be reversed")
        rows.append(row)

    canonical_id = min(item.id for item in proposals)
    reversal = create_journal_entry(
        db,
        reversal_date,
        f"REVERSAL: {original.description or 'bank proposal posting'}",
        reversing_lines(original.lines),
        source_type="bank_proposal_reversal",
        source_id=canonical_id,
        reference=original.reference or "",
        class_id=original.class_id,
    )
    now = datetime.now().astimezone()
    replacements = []
    for item, row in zip(proposals, rows):
        item.status = "reversed"
        item.reversal_transaction_id = reversal.id
        item.reversed_by = actor
        item.reversed_at = now
        item.review_note = note.strip() if note else None
        row.transaction_id = None
        row.category_account_id = None
        row.match_status = "unmatched"
        replacement = BankTransactionProposal(**_replacement_values(item, actor))
        db.add(replacement)
        replacements.append(replacement)
    db.commit()
    result = _result("reversed", proposals, reversal.id)
    result["replacement_proposal_ids"] = [item.id for item in replacements]
    return result
