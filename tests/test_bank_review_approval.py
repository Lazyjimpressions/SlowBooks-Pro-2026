"""Phase 3 bank proposal correction, approval, gates, and review UI."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.accounts import Account, AccountType
from app.models.audit import AuditLog
from app.models.banking import BankAccount, BankTransaction, BankTransactionProposal
from app.models.classes import TxnClass
from app.models.settings import Settings
from app.models.transactions import Transaction
from app.models.users import ROLE_BOOKKEEPER, ROLE_READONLY, User
from app.services import auth as auth_service


def _account(db, number, name, account_type):
    account = Account(
        account_number=number,
        name=name,
        account_type=account_type,
        balance=Decimal("0"),
    )
    db.add(account)
    db.flush()
    return account


def _row(db, suffix="1", amount="-42.10", payee="NORTHSTAR OFFICE #104"):
    cash = _account(
        db, f"101{suffix}", f"Synthetic Checking {suffix}", AccountType.ASSET
    )
    register = BankAccount(name=f"Synthetic Bank {suffix}", account=cash, balance=0)
    row = BankTransaction(
        bank_account=register,
        date=date(2026, 6, 15),
        amount=Decimal(amount),
        payee=payee,
        description=f"Imported evidence {suffix}",
        import_id=f"phase3-{suffix}",
        import_source="ofx",
        match_status="unmatched",
    )
    db.add_all([register, row])
    db.commit()
    return register, row


def _complete_payload(expense_id, class_id, *, name="Northstar Office"):
    return {
        "intent": "direct_expense",
        "posting_route": "direct",
        "normalized_counterparty": name,
        "counterparty_role": "payee",
        "counterparty_resolution": "text_only",
        "counter_account_id": expense_id,
        "class_resolution": "assigned",
        "class_id": class_id,
        "proposal_source": "human",
        "rationale": "Reviewed synthetic classification",
    }


def _create_proposal(client, row_id, payload):
    response = client.post(
        f"/api/banking/transactions/{row_id}/proposals", json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_correction_supersedes_without_mutating_imported_evidence(client, db_session):
    _, row = _row(db_session)
    expense = _account(db_session, "6119", "Synthetic Supplies", AccountType.EXPENSE)
    personal = TxnClass(name="Personal")
    db_session.add(personal)
    db_session.commit()
    original_payee, original_description = row.payee, row.description
    first = _create_proposal(
        client,
        row.id,
        {
            "counterparty_resolution": "unresolved",
            "class_resolution": "unresolved",
        },
    )

    corrected = client.put(
        f"/api/banking/proposals/{first['id']}",
        json=_complete_payload(expense.id, personal.id),
    )
    assert corrected.status_code == 201, corrected.text
    body = corrected.json()
    assert body["revision"] == 2
    assert body["supersedes_id"] == first["id"]
    assert body["proposal_source"] == "human"

    db_session.expire_all()
    old = db_session.get(BankTransactionProposal, first["id"])
    stored_row = db_session.get(BankTransaction, row.id)
    assert old.status == "superseded"
    assert old.reviewed_by == "admin"
    assert stored_row.payee == original_payee
    assert stored_row.description == original_description
    assert stored_row.transaction_id is None
    assert db_session.query(Transaction).count() == 0


def test_approval_requires_complete_valid_decisions_and_does_not_post(
    client, db_session
):
    _, row = _row(db_session)
    unresolved = _create_proposal(
        client,
        row.id,
        {
            "intent": "direct_expense",
            "posting_route": "direct",
            "counterparty_resolution": "unresolved",
            "class_resolution": "unresolved",
        },
    )
    denied = client.post(f"/api/banking/proposals/{unresolved['id']}/approve")
    assert denied.status_code == 422

    expense = _account(db_session, "6129", "Office Expense", AccountType.EXPENSE)
    personal = TxnClass(name="Personal")
    db_session.add(personal)
    db_session.commit()
    corrected = client.put(
        f"/api/banking/proposals/{unresolved['id']}",
        json=_complete_payload(expense.id, personal.id),
    ).json()

    # Review is classification, not posting; a closed accounting date does not
    # prevent approval. Phase 4 performs the closing-date check before posting.
    client.put("/api/settings", json={"closing_date": "2026-12-31"})
    approved = client.post(f"/api/banking/proposals/{corrected['id']}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewed_by"] == "admin"
    assert (
        client.post(f"/api/banking/proposals/{corrected['id']}/approve").status_code
        == 200
    )
    db_session.expire_all()
    assert db_session.get(BankTransaction, row.id).transaction_id is None
    assert db_session.query(Transaction).count() == 0

    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.table_name == "bank_transaction_proposals",
            AuditLog.record_id == corrected["id"],
            AuditLog.action == "UPDATE",
        )
        .one()
    )
    assert audit.username == "admin"
    assert "status" in audit.changed_fields


def test_transfer_requires_not_applicable_contact_and_class(client, db_session):
    first_register, first = _row(db_session, "1", "-500.00", "TRANSFER TO SAVINGS")
    _, second = _row(db_session, "2", "500.00", "TRANSFER FROM CHECKING")
    assert first_register.id != second.bank_account_id
    invalid = _create_proposal(
        client,
        first.id,
        {
            "intent": "transfer",
            "posting_route": "transfer",
            "paired_bank_transaction_id": second.id,
            "counterparty_role": "not_applicable",
            "counterparty_resolution": "not_applicable",
            "class_resolution": "personal_no_class",
        },
    )
    assert (
        client.post(f"/api/banking/proposals/{invalid['id']}/approve").status_code
        == 422
    )
    replacement = client.put(
        f"/api/banking/proposals/{invalid['id']}",
        json={
            "intent": "transfer",
            "posting_route": "transfer",
            "paired_bank_transaction_id": second.id,
            "counterparty_role": "not_applicable",
            "counterparty_resolution": "not_applicable",
            "class_resolution": "not_applicable",
            "proposal_source": "human",
        },
    ).json()
    assert (
        client.post(f"/api/banking/proposals/{replacement['id']}/approve").status_code
        == 200
    )


def test_default_personal_class_is_visible_suggestion_and_validated(client, db_session):
    _, row = _row(db_session)
    expense = _account(db_session, "6139", "Household Expense", AccountType.EXPENSE)
    personal = TxnClass(name="Personal")
    uncategorized = TxnClass(name="Uncategorized", is_system_default=True)
    db_session.add_all([personal, uncategorized])
    db_session.flush()
    db_session.add(Settings(key="default_class_id", value=str(personal.id)))
    db_session.commit()
    row.category_account_id = expense.id
    row.match_status = "auto"
    db_session.commit()

    suggested = client.post(f"/api/banking/transactions/{row.id}/suggest")
    assert suggested.status_code == 201, suggested.text
    body = suggested.json()
    assert body["class_resolution"] == "assigned"
    assert body["class_id"] == personal.id
    assert any(
        component["name"] == "company_default_class"
        for component in body["confidence_components"]
    )
    invalid = client.put(
        "/api/settings", json={"default_class_id": str(uncategorized.id)}
    )
    assert invalid.status_code == 422


def test_reject_and_supersede_are_auditable_terminal_actions(client, db_session):
    _, row = _row(db_session)
    first = _create_proposal(
        client,
        row.id,
        {"counterparty_resolution": "unresolved", "class_resolution": "unresolved"},
    )
    rejected = client.post(
        f"/api/banking/proposals/{first['id']}/reject",
        json={"note": "Wrong synthetic match"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["review_note"] == "Wrong synthetic match"

    second = _create_proposal(
        client,
        row.id,
        {"counterparty_resolution": "unresolved", "class_resolution": "unresolved"},
    )
    superseded = client.post(
        f"/api/banking/proposals/{second['id']}/supersede",
        json={"note": "Review restarted"},
    )
    assert superseded.status_code == 200
    assert superseded.json()["status"] == "superseded"


def test_bulk_approval_is_limited_to_identical_low_value_direct_items(
    client, db_session
):
    expense = _account(db_session, "6149", "Synthetic Meals", AccountType.EXPENSE)
    personal = TxnClass(name="Personal")
    db_session.add(personal)
    db_session.commit()
    ids = []
    for suffix in ("1", "2"):
        _, row = _row(db_session, suffix, "-25.00", "CEDAR CAFE")
        ids.append(
            _create_proposal(
                client,
                row.id,
                _complete_payload(expense.id, personal.id, name="Cedar Cafe"),
            )["id"]
        )
    approved = client.post(
        "/api/banking/proposals/bulk-approve", json={"proposal_ids": ids}
    )
    assert approved.status_code == 200, approved.text
    assert {item["status"] for item in approved.json()} == {"approved"}

    _, third = _row(db_session, "3", "-25.00", "CEDAR CAFE")
    _, fourth = _row(db_session, "4", "-26.00", "CEDAR CAFE")
    mismatched = [
        _create_proposal(
            client,
            third.id,
            _complete_payload(expense.id, personal.id, name="Cedar Cafe"),
        )["id"],
        _create_proposal(
            client,
            fourth.id,
            _complete_payload(expense.id, personal.id, name="Cedar Cafe"),
        )["id"],
    ]
    refused = client.post(
        "/api/banking/proposals/bulk-approve", json={"proposal_ids": mismatched}
    )
    assert refused.status_code == 422


def test_bookkeeper_can_review_but_readonly_cannot(client, db_session):
    expense = _account(db_session, "6159", "Synthetic Expense", AccountType.EXPENSE)
    personal = TxnClass(name="Personal")
    db_session.add(personal)
    _, row = _row(db_session)
    for username, role in (("keeper", ROLE_BOOKKEEPER), ("viewer", ROLE_READONLY)):
        db_session.add(
            User(
                username=username,
                display_name=username.title(),
                password_hash=auth_service.hash_password("role-password-1"),
                role=role,
                is_active=True,
            )
        )
    db_session.commit()
    proposal = _create_proposal(
        client, row.id, _complete_payload(expense.id, personal.id)
    )

    client.post("/api/auth/logout")
    client.post(
        "/api/auth/login",
        json={"username": "viewer", "password": "role-password-1"},
    )
    assert client.get("/api/banking/review?status=proposed").status_code == 200
    assert (
        client.post(f"/api/banking/proposals/{proposal['id']}/approve").status_code
        == 403
    )

    client.post("/api/auth/logout")
    client.post(
        "/api/auth/login",
        json={"username": "keeper", "password": "role-password-1"},
    )
    approved = client.post(f"/api/banking/proposals/{proposal['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["reviewed_by"] == "keeper"


def test_review_ui_exposes_every_required_field_and_gates_contact_creation():
    root = Path(__file__).resolve().parent.parent
    source = (root / "app/static/js/bank_review.js").read_text()
    for field in (
        "intent",
        "posting_route",
        "counterparty_resolution",
        "counterparty_role",
        "counter_account_id",
        "class_resolution",
        "class_id",
        "rationale",
    ):
        assert f'name="{field}"' in source
    assert "Imported evidence — read only" in source
    assert "/check-duplicate?name=" in source
    assert "This creates a real record" in source
    assert "query: { force: true }" not in source
    assert "Save &amp; Approve" in source


def test_phase_three_migration_round_trip(tmp_path):
    import sqlite3

    from alembic import command
    from alembic.config import Config

    database = tmp_path / "review-approval.db"
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.attributes["database_url"] = "sqlite:///" + database.as_posix()
    command.upgrade(config, "head")
    connection = sqlite3.connect(database)
    columns = {
        row[1]
        for row in connection.execute("pragma table_info(bank_transaction_proposals)")
    }
    table_sql = connection.execute(
        "select sql from sqlite_master where type='table' and name='bank_transaction_proposals'"
    ).fetchone()[0]
    connection.close()
    assert "review_note" in columns
    assert "not_applicable" in table_sql

    command.downgrade(config, "a9b0c1d2e3f4")
    connection = sqlite3.connect(database)
    columns = {
        row[1]
        for row in connection.execute("pragma table_info(bank_transaction_proposals)")
    }
    connection.close()
    assert "review_note" not in columns
