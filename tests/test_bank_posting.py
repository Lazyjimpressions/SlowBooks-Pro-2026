"""Atomic and idempotent bank-feed posting and transfer pairing."""

from datetime import date as dt_date
from decimal import Decimal

import pytest

from app.models.banking import BankAccount, BankTransaction
from app.models.classes import TxnClass
from app.models.transactions import Transaction, TransactionLine
from app.services.bank_posting import post_bank_transaction, post_bank_transfer


def _register(db, account, name):
    row = BankAccount(name=name, account_id=account.id, balance=Decimal("0"))
    db.add(row)
    db.commit()
    return row


def _feed(db, register, amount, date="2026-08-17", payee="Feed row"):
    row = BankTransaction(
        bank_account_id=register.id,
        date=dt_date.fromisoformat(date),
        amount=Decimal(amount),
        payee=payee,
        import_id=f"test-{register.id}-{date}-{amount}-{payee}",
        import_source="csv_test",
        match_status="unmatched",
    )
    db.add(row)
    db.commit()
    return row


def test_positive_feed_posts_income_with_class_once(client, db_session, seed_accounts):
    savings = seed_accounts["1010"]
    income = seed_accounts["4000"]
    register = _register(db_session, savings, "Savings")
    feed = _feed(db_session, register, "9600.00", payee="Consulting deposit")
    cls = TxnClass(name="Business")
    db_session.add(cls)
    db_session.commit()

    payload = {"counter_account_id": income.id, "class_id": cls.id}
    first = post_bank_transaction(
        db_session, feed, payload["counter_account_id"], class_id=payload["class_id"]
    )
    assert first["status"] == "posted"
    ledger_id = first["transaction_id"]

    db_session.expire_all()
    linked = db_session.get(BankTransaction, feed.id)
    assert linked.transaction_id == ledger_id
    assert linked.category_account_id == income.id
    lines = (
        db_session.query(TransactionLine)
        .filter(TransactionLine.transaction_id == ledger_id)
        .all()
    )
    assert {(line.account_id, line.debit, line.credit) for line in lines} == {
        (savings.id, Decimal("9600.00"), Decimal("0.00")),
        (income.id, Decimal("0.00"), Decimal("9600.00")),
    }
    assert all(line.class_id == cls.id for line in lines)

    second = post_bank_transaction(
        db_session, feed, payload["counter_account_id"], class_id=payload["class_id"]
    )
    assert second["status"] == "already_posted"
    assert db_session.query(Transaction).filter_by(source_type="bank_feed").count() == 1


def test_opposite_feed_rows_post_as_one_transfer(client, db_session, seed_accounts):
    checking = seed_accounts["1000"]
    savings = seed_accounts["1010"]
    checking_register = _register(db_session, checking, "Checking")
    savings_register = _register(db_session, savings, "Savings")
    incoming = _feed(db_session, checking_register, "25000.00", date="2026-05-27")
    outgoing = _feed(db_session, savings_register, "-25000.00", date="2026-05-27")

    response = post_bank_transfer(db_session, incoming, outgoing)
    ledger_id = response["transaction_id"]

    db_session.expire_all()
    assert db_session.get(BankTransaction, incoming.id).transaction_id == ledger_id
    assert db_session.get(BankTransaction, outgoing.id).transaction_id == ledger_id
    lines = (
        db_session.query(TransactionLine)
        .filter(TransactionLine.transaction_id == ledger_id)
        .all()
    )
    assert {(line.account_id, line.debit, line.credit) for line in lines} == {
        (checking.id, Decimal("25000.00"), Decimal("0.00")),
        (savings.id, Decimal("0.00"), Decimal("25000.00")),
    }

    retry = post_bank_transfer(db_session, incoming, outgoing)
    assert retry["status"] == "already_posted"
    assert (
        db_session.query(Transaction).filter_by(source_type="bank_transfer").count()
        == 1
    )


def test_single_post_rejects_another_linked_bank_account(
    client, db_session, seed_accounts
):
    checking = seed_accounts["1000"]
    savings = seed_accounts["1010"]
    checking_register = _register(db_session, checking, "Checking")
    _register(db_session, savings, "Savings")
    feed = _feed(db_session, checking_register, "-10.00")

    with pytest.raises(ValueError, match="bank-transfer endpoint"):
        post_bank_transaction(db_session, feed, savings.id)
    assert db_session.query(Transaction).filter_by(source_type="bank_feed").count() == 0


def test_negative_card_feed_debits_expense_and_credits_liability(
    client, db_session, seed_accounts
):
    card = seed_accounts["2100"]
    expense = seed_accounts["6400"]
    register = _register(db_session, card, "Credit card")
    feed = _feed(db_session, register, "-89.99", payee="Office supplier")

    response = post_bank_transaction(db_session, feed, expense.id)
    ledger_id = response["transaction_id"]
    lines = (
        db_session.query(TransactionLine)
        .filter(TransactionLine.transaction_id == ledger_id)
        .all()
    )
    assert {(line.account_id, line.debit, line.credit) for line in lines} == {
        (expense.id, Decimal("89.99"), Decimal("0.00")),
        (card.id, Decimal("0.00"), Decimal("89.99")),
    }


def test_transfer_rejects_amount_mismatch(client, db_session, seed_accounts):
    checking_register = _register(db_session, seed_accounts["1000"], "Checking")
    savings_register = _register(db_session, seed_accounts["1010"], "Savings")
    first = _feed(db_session, checking_register, "10.00")
    second = _feed(db_session, savings_register, "-9.00")

    with pytest.raises(ValueError, match="equal and opposite"):
        post_bank_transfer(db_session, first, second)
