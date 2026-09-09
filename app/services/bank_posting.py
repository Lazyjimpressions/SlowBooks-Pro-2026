"""Atomic, idempotent posting for imported bank-feed evidence."""

from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.accounts import Account
from app.models.banking import BankAccount, BankTransaction
from app.models.classes import TxnClass
from app.models.transactions import Transaction
from app.services.accounting import create_journal_entry
from app.services.closing_date import check_closing_date


def _linked_account(db: Session, feed_row: BankTransaction) -> Account:
    register = db.get(BankAccount, feed_row.bank_account_id)
    if not register or not register.account_id:
        raise ValueError("The bank register must be linked to a chart account")
    account = db.get(Account, register.account_id)
    if not account or not account.is_active:
        raise ValueError("The bank register's linked chart account is unavailable")
    return account


def _validate_class(db: Session, class_id: int | None) -> None:
    if class_id is not None and db.get(TxnClass, class_id) is None:
        raise ValueError(f"Class {class_id} not found")


def _existing_result(feed_rows: list[BankTransaction]) -> dict | None:
    linked = {row.transaction_id for row in feed_rows if row.transaction_id}
    if not linked:
        return None
    if len(linked) == 1 and all(row.transaction_id in linked for row in feed_rows):
        return {
            "status": "already_posted",
            "transaction_id": linked.pop(),
            "bank_transaction_ids": [row.id for row in feed_rows],
        }
    raise ValueError("One or more bank rows are already linked to another posting")


def post_bank_transaction(
    db: Session,
    feed_row: BankTransaction,
    counter_account_id: int,
    *,
    class_id: int | None = None,
    description: str | None = None,
    reference: str | None = None,
    source_type: str = "bank_feed",
    source_id: int | None = None,
    commit: bool = True,
) -> dict:
    """Post one feed row against a non-bank counter-account exactly once."""
    existing = _existing_result([feed_row])
    if existing:
        return existing

    linked_account = _linked_account(db, feed_row)
    counter = db.get(Account, counter_account_id)
    if not counter or not counter.is_active:
        raise ValueError(f"Counter-account {counter_account_id} not found or inactive")
    if counter.id == linked_account.id:
        raise ValueError("The counter-account must differ from the bank account")
    if (
        db.query(BankAccount.id)
        .filter(
            BankAccount.account_id == counter.id,
            BankAccount.id != feed_row.bank_account_id,
            BankAccount.is_active.is_(True),
        )
        .first()
    ):
        raise ValueError("Use the bank-transfer endpoint for another bank register")

    _validate_class(db, class_id)
    check_closing_date(db, feed_row.date)
    amount = Decimal(feed_row.amount)
    if amount == 0:
        raise ValueError("A zero-amount bank row cannot be posted")
    absolute = abs(amount)
    if amount > 0:
        bank_debit, bank_credit = absolute, Decimal("0")
        counter_debit, counter_credit = Decimal("0"), absolute
    else:
        bank_debit, bank_credit = Decimal("0"), absolute
        counter_debit, counter_credit = absolute, Decimal("0")

    memo = description or feed_row.description or feed_row.payee or "Bank feed posting"
    txn = create_journal_entry(
        db,
        feed_row.date,
        memo,
        [
            {
                "account_id": linked_account.id,
                "debit": bank_debit,
                "credit": bank_credit,
                "description": memo,
            },
            {
                "account_id": counter.id,
                "debit": counter_debit,
                "credit": counter_credit,
                "description": memo,
            },
        ],
        source_type=source_type,
        source_id=feed_row.id if source_id is None else source_id,
        reference=reference or feed_row.import_id or "",
        class_id=class_id,
    )
    feed_row.transaction_id = txn.id
    feed_row.category_account_id = counter.id
    feed_row.match_status = "manual"
    if not commit:
        return {
            "status": "posted",
            "transaction_id": txn.id,
            "bank_transaction_ids": [feed_row.id],
        }
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = (
            db.query(Transaction)
            .filter(
                Transaction.source_type == source_type,
                Transaction.source_id
                == (feed_row.id if source_id is None else source_id),
            )
            .first()
        )
        if winner:
            return {
                "status": "already_posted",
                "transaction_id": winner.id,
                "bank_transaction_ids": [feed_row.id],
            }
        raise
    return {
        "status": "posted",
        "transaction_id": txn.id,
        "bank_transaction_ids": [feed_row.id],
    }


def post_bank_transfer(
    db: Session,
    first: BankTransaction,
    second: BankTransaction,
    *,
    description: str | None = None,
    reference: str | None = None,
    source_type: str = "bank_transfer",
    source_id: int | None = None,
    commit: bool = True,
) -> dict:
    """Post two opposite feed rows as one balance-sheet transfer."""
    if first.id == second.id:
        raise ValueError("A transfer requires two different bank rows")
    existing = _existing_result([first, second])
    if existing:
        return existing

    if first.bank_account_id == second.bank_account_id:
        raise ValueError("Transfer rows must belong to different bank registers")
    first_amount = Decimal(first.amount)
    second_amount = Decimal(second.amount)
    if first_amount == 0 or first_amount + second_amount != 0:
        raise ValueError("Transfer rows must have equal and opposite amounts")

    outgoing, incoming = (first, second) if first_amount < 0 else (second, first)
    outgoing_account = _linked_account(db, outgoing)
    incoming_account = _linked_account(db, incoming)
    if outgoing_account.id == incoming_account.id:
        raise ValueError("Transfer registers must use different chart accounts")

    check_closing_date(db, outgoing.date)
    check_closing_date(db, incoming.date)
    amount = abs(Decimal(outgoing.amount))
    memo = description or f"Transfer: {outgoing.payee or ''}".strip()
    txn = create_journal_entry(
        db,
        outgoing.date,
        memo,
        [
            {
                "account_id": incoming_account.id,
                "debit": amount,
                "credit": Decimal("0"),
                "description": memo,
            },
            {
                "account_id": outgoing_account.id,
                "debit": Decimal("0"),
                "credit": amount,
                "description": memo,
            },
        ],
        source_type=source_type,
        source_id=outgoing.id if source_id is None else source_id,
        reference=reference or outgoing.import_id or "",
    )
    outgoing.transaction_id = txn.id
    incoming.transaction_id = txn.id
    outgoing.category_account_id = incoming_account.id
    incoming.category_account_id = outgoing_account.id
    outgoing.match_status = "manual"
    incoming.match_status = "manual"
    if not commit:
        return {
            "status": "posted",
            "transaction_id": txn.id,
            "bank_transaction_ids": [first.id, second.id],
        }
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = (
            db.query(Transaction)
            .filter(
                Transaction.source_type == source_type,
                Transaction.source_id
                == (outgoing.id if source_id is None else source_id),
            )
            .first()
        )
        if winner:
            return {
                "status": "already_posted",
                "transaction_id": winner.id,
                "bank_transaction_ids": [outgoing.id, incoming.id],
            }
        raise
    return {
        "status": "posted",
        "transaction_id": txn.id,
        "bank_transaction_ids": [outgoing.id, incoming.id],
    }
