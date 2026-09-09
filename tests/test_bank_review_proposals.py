"""Phase 1 bank-review proposal persistence and API contract."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.accounts import Account, AccountType
from app.models.audit import AuditLog
from app.models.banking import (
    BankAccount,
    BankTransaction,
    BankTransactionProposal,
)
from app.models.classes import TxnClass
from app.models.contacts import Customer, Vendor
from app.models.transactions import Transaction


def _bank_row(db_session, amount=Decimal("125.00")):
    cash = Account(
        name="Synthetic Checking",
        account_number="1019",
        account_type=AccountType.ASSET,
        balance=Decimal("0"),
    )
    bank = BankAccount(name="Synthetic Bank", account=cash, balance=amount)
    row = BankTransaction(
        bank_account=bank,
        date=date(2026, 1, 15),
        amount=amount,
        payee="CEDAR WORKSHOP",
        description="SQ *CEDAR WORKSHOP 4821",
        import_id="synthetic-fitid-1",
        import_source="ofx",
    )
    db_session.add_all([cash, bank, row])
    db_session.commit()
    return bank, row


def test_proposal_is_non_posting_and_moves_row_out_of_unresolved_queue(
    client, db_session
):
    bank, row = _bank_row(db_session)
    initial_balance = bank.balance

    unresolved = client.get("/api/banking/review?status=unresolved")
    assert unresolved.status_code == 200
    assert [item["transaction"]["id"] for item in unresolved.json()] == [row.id]

    response = client.post(
        f"/api/banking/transactions/{row.id}/proposals",
        json={
            "intent": "direct_income",
            "posting_route": "direct",
            "counterparty_resolution": "text_only",
            "counterparty_role": "payer",
            "normalized_counterparty": "Cedar Workshop",
            "class_resolution": "personal_no_class",
            "proposal_source": "human",
            "confidence": "0.7500",
            "rationale": "Synthetic review fixture",
        },
    )
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["revision"] == 1
    assert proposal["status"] == "proposed"
    assert proposal["class_resolution"] == "personal_no_class"
    assert proposal["class_id"] is None
    assert proposal["created_by"]

    db_session.expire_all()
    stored_row = db_session.get(BankTransaction, row.id)
    assert stored_row.transaction_id is None
    assert db_session.get(BankAccount, bank.id).balance == initial_balance
    assert db_session.query(Transaction).count() == 0
    audit_entry = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.table_name == "bank_transaction_proposals",
            AuditLog.record_id == proposal["id"],
            AuditLog.action == "INSERT",
        )
        .one()
    )
    assert audit_entry.username == proposal["created_by"]

    assert client.get("/api/banking/review?status=unresolved").json() == []
    proposed = client.get("/api/banking/review?status=proposed").json()
    assert proposed[0]["active_proposal"]["id"] == proposal["id"]

    detail = client.get(f"/api/banking/transactions/{row.id}/review")
    assert detail.status_code == 200
    assert detail.json()["proposal_history"][0]["id"] == proposal["id"]


def test_only_one_active_proposal_per_bank_row(client, db_session):
    _, row = _bank_row(db_session)
    payload = {
        "counterparty_resolution": "unresolved",
        "class_resolution": "unresolved",
    }
    assert (
        client.post(
            f"/api/banking/transactions/{row.id}/proposals", json=payload
        ).status_code
        == 201
    )
    duplicate = client.post(
        f"/api/banking/transactions/{row.id}/proposals", json=payload
    )
    assert duplicate.status_code == 409

    db_session.add(
        BankTransactionProposal(
            bank_transaction_id=row.id,
            revision=2,
            status="approved",
            intent="unknown",
            posting_route="hold",
            counterparty_resolution="unresolved",
            class_resolution="unresolved",
            proposal_source="human",
            created_by="test",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_class_and_contact_resolution_are_explicit(client, db_session):
    _, row = _bank_row(db_session)
    txn_class = TxnClass(name="Sch C - Synthetic")
    customer = Customer(name="Synthetic Customer")
    vendor = Vendor(name="Synthetic Vendor")
    db_session.add_all([txn_class, customer, vendor])
    db_session.commit()

    invalid_class = client.post(
        f"/api/banking/transactions/{row.id}/proposals",
        json={"class_resolution": "assigned"},
    )
    assert invalid_class.status_code == 422

    invalid_contact = client.post(
        f"/api/banking/transactions/{row.id}/proposals",
        json={
            "counterparty_resolution": "customer",
            "customer_id": customer.id,
            "vendor_id": vendor.id,
            "class_resolution": "assigned",
            "class_id": txn_class.id,
        },
    )
    assert invalid_contact.status_code == 422

    valid = client.post(
        f"/api/banking/transactions/{row.id}/proposals",
        json={
            "intent": "direct_income",
            "posting_route": "direct",
            "counterparty_resolution": "customer",
            "counterparty_role": "payer",
            "customer_id": customer.id,
            "class_resolution": "assigned",
            "class_id": txn_class.id,
        },
    )
    assert valid.status_code == 201, valid.text
    assert valid.json()["customer_id"] == customer.id
    assert valid.json()["vendor_id"] is None


def test_database_rejects_ambiguous_class_and_contact_resolution(db_session):
    _, row = _bank_row(db_session)
    txn_class = TxnClass(name="Sch C - Synthetic")
    customer = Customer(name="Synthetic Customer")
    vendor = Vendor(name="Synthetic Vendor")
    db_session.add_all([txn_class, customer, vendor])
    db_session.commit()
    db_session.add(
        BankTransactionProposal(
            bank_transaction_id=row.id,
            revision=1,
            status="proposed",
            intent="unknown",
            posting_route="hold",
            counterparty_resolution="unresolved",
            class_resolution="personal_no_class",
            class_id=txn_class.id,
            proposal_source="human",
            created_by="test",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(
        BankTransactionProposal(
            bank_transaction_id=row.id,
            revision=1,
            status="proposed",
            intent="unknown",
            posting_route="hold",
            counterparty_resolution="customer",
            customer_id=customer.id,
            vendor_id=vendor.id,
            class_resolution="unresolved",
            proposal_source="human",
            created_by="test",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_bank_proposal_migration_upgrades_and_downgrades(tmp_path):
    import sqlite3

    from alembic import command
    from alembic.config import Config

    database = tmp_path / "proposal-migration.db"
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.attributes["database_url"] = "sqlite:///" + database.as_posix()

    command.upgrade(config, "head")
    connection = sqlite3.connect(database)
    table_names = {
        row[0]
        for row in connection.execute(
            "select name from sqlite_master where type = 'table'"
        )
    }
    index_sql = connection.execute(
        "select sql from sqlite_master where type = 'index' "
        "and name = 'uq_bank_transaction_proposal_active'"
    ).fetchone()[0]
    connection.close()
    assert "bank_transaction_proposals" in table_names
    assert "WHERE status IN ('proposed', 'approved')" in index_sql

    command.downgrade(config, "e7f8a9b0c1d2")
    connection = sqlite3.connect(database)
    table_names = {
        row[0]
        for row in connection.execute(
            "select name from sqlite_master where type = 'table'"
        )
    }
    connection.close()
    assert "bank_transaction_proposals" not in table_names
