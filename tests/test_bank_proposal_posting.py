"""Phase 4 approved-proposal posting, provenance, holds, and reversal."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.banking import BankAccount, BankTransaction, BankTransactionProposal
from app.models.classes import TxnClass
from app.models.contacts import Customer, Vendor
from app.models.transactions import (
    Transaction,
    TransactionCounterparty,
    TransactionLine,
)
from app.models.users import ROLE_READONLY, User
from app.services import auth as auth_service


def _register(db, account, name):
    register = BankAccount(name=name, account_id=account.id, balance=Decimal("0"))
    db.add(register)
    db.commit()
    return register


def _row(db, register, amount, suffix, payee="CEDAR WORKSHOP"):
    row = BankTransaction(
        bank_account_id=register.id,
        date=date(2026, 8, 18),
        amount=Decimal(amount),
        payee=payee,
        description=f"Synthetic imported evidence {suffix}",
        import_id=f"phase4-{suffix}",
        import_source="synthetic",
        match_status="unmatched",
    )
    db.add(row)
    db.commit()
    return row


def _approved(client, row, **overrides):
    payload = {
        "intent": "direct_expense",
        "posting_route": "direct",
        "normalized_counterparty": "Cedar Workshop",
        "counterparty_role": "payee",
        "counterparty_resolution": "text_only",
        "counter_account_id": overrides.pop("counter_account_id"),
        "class_resolution": "assigned",
        "class_id": overrides.pop("class_id"),
        "proposal_source": "human",
        "rationale": "Synthetic reviewed decision",
        **overrides,
    }
    created = client.post(f"/api/banking/transactions/{row.id}/proposals", json=payload)
    assert created.status_code == 201, created.text
    proposal = created.json()
    approved = client.post(f"/api/banking/proposals/{proposal['id']}/approve")
    assert approved.status_code == 200, approved.text
    return approved.json()


def _lines(db, transaction_id):
    return (
        db.query(TransactionLine)
        .filter(TransactionLine.transaction_id == transaction_id)
        .all()
    )


def test_direct_income_posts_once_with_customer_and_class(
    client, db_session, seed_accounts
):
    register = _register(db_session, seed_accounts["1000"], "Synthetic Checking")
    row = _row(db_session, register, "850.00", "income")
    customer = Customer(name="Cedar Workshop", is_active=True)
    business = TxnClass(name="Sch C - Example")
    db_session.add_all([customer, business])
    db_session.commit()
    proposal = _approved(
        client,
        row,
        intent="direct_income",
        counterparty_role="payer",
        counterparty_resolution="customer",
        customer_id=customer.id,
        counter_account_id=seed_accounts["4000"].id,
        class_id=business.id,
    )

    posted = client.post(f"/api/banking/proposals/{proposal['id']}/post")
    assert posted.status_code == 200, posted.text
    assert posted.json()["status"] == "posted"
    transaction_id = posted.json()["transaction_id"]

    db_session.expire_all()
    stored = db_session.get(BankTransactionProposal, proposal["id"])
    assert stored.status == "posted"
    assert stored.posted_transaction_id == transaction_id
    assert stored.bank_transaction.transaction_id == transaction_id
    assert stored.posted_counterparty.customer_id == customer.id
    assert stored.posted_counterparty.role == "payer"
    assert all(
        line.class_id == business.id for line in _lines(db_session, transaction_id)
    )
    assert {
        (line.account_id, line.debit, line.credit)
        for line in _lines(db_session, transaction_id)
    } == {
        (seed_accounts["1000"].id, Decimal("850.00"), Decimal("0.00")),
        (seed_accounts["4000"].id, Decimal("0.00"), Decimal("850.00")),
    }

    retry = client.post(f"/api/banking/proposals/{proposal['id']}/post")
    assert retry.status_code == 200
    assert retry.json()["status"] == "already_posted"
    assert (
        db_session.query(Transaction).filter_by(source_type="bank_income").count() == 1
    )
    report = client.get(
        "/api/reports/profit-loss-by-class?start_date=2026-08-01&end_date=2026-08-31"
    ).json()
    by_name = {item["class_name"]: item for item in report["classes"]}
    assert by_name["Sch C - Example"]["income"] == 850.0


def test_card_expense_appears_in_expenses_with_vendor(
    client, db_session, seed_accounts
):
    register = _register(db_session, seed_accounts["2100"], "Synthetic Card")
    row = _row(db_session, register, "-64.25", "expense", "NORTHSTAR OFFICE")
    vendor = Vendor(name="Northstar Office", is_active=True)
    personal = TxnClass(name="Personal")
    db_session.add_all([vendor, personal])
    db_session.commit()
    proposal = _approved(
        client,
        row,
        normalized_counterparty="Northstar Office",
        counterparty_resolution="vendor",
        vendor_id=vendor.id,
        counter_account_id=seed_accounts["6400"].id,
        class_id=personal.id,
    )

    response = client.post(f"/api/banking/proposals/{proposal['id']}/post")
    assert response.status_code == 200, response.text
    transaction_id = response.json()["transaction_id"]
    expense = client.get(f"/api/expenses/{transaction_id}")
    assert expense.status_code == 200
    assert expense.json()["vendor_id"] == vendor.id
    assert expense.json()["amount"] == 64.25
    assert client.post(f"/api/expenses/{transaction_id}/void").status_code == 409
    counterparty = db_session.query(TransactionCounterparty).one()
    assert counterparty.display_name == "Northstar Office"
    assert counterparty.vendor_id == vendor.id
    report = client.get(
        "/api/reports/profit-loss-by-class?start_date=2026-08-01&end_date=2026-08-31"
    ).json()
    by_name = {item["class_name"]: item for item in report["classes"]}
    assert by_name["Personal"]["expenses"] == 64.25


def test_ar_candidate_stays_held_and_legacy_endpoint_requires_approval(
    client, db_session, seed_accounts
):
    register = _register(db_session, seed_accounts["1000"], "Synthetic Checking")
    row = _row(db_session, register, "125.00", "held")
    no_approval = client.post(
        f"/api/banking/transactions/{row.id}/post",
        json={"counter_account_id": seed_accounts["4000"].id},
    )
    assert no_approval.status_code == 409

    customer = Customer(name="Cedar Workshop", is_active=True)
    db_session.add(customer)
    db_session.commit()
    held = _approved(
        client,
        row,
        intent="customer_payment",
        posting_route="customer_payment",
        counterparty_role="payer",
        counterparty_resolution="customer",
        customer_id=customer.id,
        counter_account_id=None,
        class_resolution="not_applicable",
        class_id=None,
    )
    refused = client.post(f"/api/banking/proposals/{held['id']}/post")
    assert refused.status_code == 409
    assert "domain workflow" in refused.json()["detail"]
    assert db_session.query(Transaction).count() == 0


def test_mutually_approved_transfer_posts_without_class_or_contact(
    client, db_session, seed_accounts
):
    checking = _register(db_session, seed_accounts["1000"], "Synthetic Checking")
    savings = _register(db_session, seed_accounts["1010"], "Synthetic Savings")
    outgoing = _row(db_session, checking, "-500.00", "transfer-out")
    incoming = _row(db_session, savings, "500.00", "transfer-in")
    proposals = []
    for row, pair in ((outgoing, incoming), (incoming, outgoing)):
        response = client.post(
            f"/api/banking/transactions/{row.id}/proposals",
            json={
                "intent": "transfer",
                "posting_route": "transfer",
                "counterparty_role": "not_applicable",
                "counterparty_resolution": "not_applicable",
                "class_resolution": "not_applicable",
                "paired_bank_transaction_id": pair.id,
            },
        )
        assert response.status_code == 201
        proposal = response.json()
        approved = client.post(f"/api/banking/proposals/{proposal['id']}/approve")
        assert approved.status_code == 200, approved.text
        proposals.append(approved.json())

    posted = client.post(f"/api/banking/proposals/{proposals[0]['id']}/post")
    assert posted.status_code == 200, posted.text
    assert set(posted.json()["proposal_ids"]) == {item["id"] for item in proposals}
    transaction_id = posted.json()["transaction_id"]
    db_session.expire_all()
    assert all(
        db_session.get(BankTransactionProposal, item["id"]).status == "posted"
        for item in proposals
    )
    assert db_session.query(TransactionCounterparty).count() == 0
    assert all(line.class_id is None for line in _lines(db_session, transaction_id))
    retry = client.post(f"/api/banking/proposals/{proposals[1]['id']}/post")
    assert retry.status_code == 200
    assert retry.json()["status"] == "already_posted"
    assert set(retry.json()["proposal_ids"]) == {item["id"] for item in proposals}
    reversed_once = client.post(
        f"/api/banking/proposals/{proposals[0]['id']}/reverse",
        json={"reversal_date": "2026-08-19"},
    )
    assert reversed_once.status_code == 200
    assert len(reversed_once.json()["replacement_proposal_ids"]) == 2
    reversed_retry = client.post(
        f"/api/banking/proposals/{proposals[1]['id']}/reverse",
        json={"reversal_date": "2026-08-19"},
    )
    assert reversed_retry.status_code == 200
    assert reversed_retry.json()["status"] == "already_reversed"
    assert set(reversed_retry.json()["proposal_ids"]) == {
        item["id"] for item in proposals
    }
    assert set(reversed_retry.json()["replacement_proposal_ids"]) == set(
        reversed_once.json()["replacement_proposal_ids"]
    )


def test_readonly_cannot_post_or_reverse_approved_proposal(
    client, db_session, seed_accounts
):
    register = _register(db_session, seed_accounts["1000"], "Synthetic Checking")
    row = _row(db_session, register, "-45.00", "readonly")
    personal = TxnClass(name="Personal")
    viewer = User(
        username="phase4-viewer",
        display_name="Phase 4 Viewer",
        password_hash=auth_service.hash_password("role-password-1"),
        role=ROLE_READONLY,
        is_active=True,
    )
    db_session.add_all([personal, viewer])
    db_session.commit()
    proposal = _approved(
        client,
        row,
        counter_account_id=seed_accounts["6400"].id,
        class_id=personal.id,
    )

    client.post("/api/auth/logout")
    logged_in = client.post(
        "/api/auth/login",
        json={"username": "phase4-viewer", "password": "role-password-1"},
    )
    assert logged_in.status_code == 200
    assert (
        client.post(f"/api/banking/proposals/{proposal['id']}/post").status_code == 403
    )
    assert (
        client.post(
            f"/api/banking/proposals/{proposal['id']}/reverse",
            json={"reversal_date": "2026-08-19"},
        ).status_code
        == 403
    )


def test_reversal_reopens_row_and_allows_corrected_repost(
    client, db_session, seed_accounts
):
    register = _register(db_session, seed_accounts["1000"], "Synthetic Checking")
    row = _row(db_session, register, "-80.00", "reverse", "NORTHSTAR OFFICE")
    personal = TxnClass(name="Personal")
    db_session.add(personal)
    db_session.commit()
    proposal = _approved(
        client,
        row,
        counter_account_id=seed_accounts["6400"].id,
        class_id=personal.id,
    )
    posted = client.post(f"/api/banking/proposals/{proposal['id']}/post").json()

    reversed_response = client.post(
        f"/api/banking/proposals/{proposal['id']}/reverse",
        json={"reversal_date": "2026-08-19", "note": "Wrong expense account"},
    )
    assert reversed_response.status_code == 200, reversed_response.text
    body = reversed_response.json()
    assert body["status"] == "reversed"
    assert len(body["replacement_proposal_ids"]) == 1

    db_session.expire_all()
    original = db_session.get(BankTransactionProposal, proposal["id"])
    replacement = db_session.get(
        BankTransactionProposal, body["replacement_proposal_ids"][0]
    )
    assert original.status == "reversed"
    assert original.review_note == "Wrong expense account"
    assert replacement.status == "proposed"
    assert replacement.supersedes_id == original.id
    assert replacement.class_id == personal.id
    assert db_session.get(BankTransaction, row.id).transaction_id is None

    original_lines = _lines(db_session, posted["transaction_id"])
    reversal_lines = _lines(db_session, body["transaction_id"])
    assert (
        sum(
            (line.debit - line.credit for line in original_lines + reversal_lines),
            Decimal("0"),
        )
        == 0
    )

    corrected = client.put(
        f"/api/banking/proposals/{replacement.id}",
        json={
            "intent": "direct_expense",
            "posting_route": "direct",
            "normalized_counterparty": "Northstar Office",
            "counterparty_role": "payee",
            "counterparty_resolution": "text_only",
            "counter_account_id": seed_accounts["6500"].id,
            "class_resolution": "assigned",
            "class_id": personal.id,
        },
    )
    assert corrected.status_code == 201, corrected.text
    corrected_id = corrected.json()["id"]
    assert (
        client.post(f"/api/banking/proposals/{corrected_id}/approve").status_code == 200
    )
    reposted = client.post(f"/api/banking/proposals/{corrected_id}/post")
    assert reposted.status_code == 200, reposted.text
    assert reposted.json()["transaction_id"] != posted["transaction_id"]


def test_reconciled_row_cannot_be_reversed(client, db_session, seed_accounts):
    register = _register(db_session, seed_accounts["1000"], "Synthetic Checking")
    row = _row(db_session, register, "-40.00", "reconciled")
    personal = TxnClass(name="Personal")
    db_session.add(personal)
    db_session.commit()
    proposal = _approved(
        client,
        row,
        counter_account_id=seed_accounts["6400"].id,
        class_id=personal.id,
    )
    assert (
        client.post(f"/api/banking/proposals/{proposal['id']}/post").status_code == 200
    )
    row.reconciled = True
    db_session.commit()
    refused = client.post(
        f"/api/banking/proposals/{proposal['id']}/reverse",
        json={"reversal_date": "2026-08-19"},
    )
    assert refused.status_code == 409


def test_phase_four_migration_round_trip(tmp_path):
    import sqlite3

    from alembic import command
    from alembic.config import Config

    database = tmp_path / "proposal-posting.db"
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.attributes["database_url"] = "sqlite:///" + database.as_posix()
    command.upgrade(config, "head")
    connection = sqlite3.connect(database)
    proposal_columns = {
        row[1]
        for row in connection.execute("pragma table_info(bank_transaction_proposals)")
    }
    counterparty_columns = {
        row[1]
        for row in connection.execute("pragma table_info(transaction_counterparties)")
    }
    connection.close()
    assert {
        "posted_transaction_id",
        "reversal_transaction_id",
        "reversed_by",
    } <= proposal_columns
    assert {"transaction_id", "role", "proposal_id"} <= counterparty_columns

    command.downgrade(config, "b0c1d2e3f4a5")
    connection = sqlite3.connect(database)
    tables = {
        row[0]
        for row in connection.execute(
            "select name from sqlite_master where type='table'"
        )
    }
    connection.close()
    assert "transaction_counterparties" not in tables
