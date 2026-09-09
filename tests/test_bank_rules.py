"""Phase 5 Bank Rules as scoped, non-posting review memory."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.accounts import Account, AccountType
from app.models.bank_rules import BankRule
from app.models.banking import BankAccount, BankTransaction, BankTransactionProposal
from app.models.classes import TxnClass
from app.models.contacts import Customer, Vendor
from app.models.transactions import Transaction


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


def _register(db, number, name):
    account = _account(db, number, name, AccountType.ASSET)
    register = BankAccount(name=name, account=account, balance=Decimal("0"))
    db.add(register)
    db.flush()
    return register


def _row(db, register, suffix, amount, payee):
    row = BankTransaction(
        bank_account=register,
        date=date(2026, 8, 20),
        amount=Decimal(amount),
        payee=payee,
        description=f"Synthetic rule evidence {suffix}",
        import_id=f"phase5-{suffix}",
        import_source="synthetic",
        match_status="unmatched",
    )
    db.add(row)
    db.commit()
    return row


def _create_rule(client, **overrides):
    payload = {
        "name": "Synthetic office rule",
        "pattern": "NORTHSTAR OFFICE",
        "rule_type": "exact",
        "match_field": "normalized",
        "direction": "withdrawal",
        "priority": 100,
        **overrides,
    }
    response = client.post("/api/bank-rules", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_priority_register_direction_amount_and_normalized_scope(client, db_session):
    checking = _register(db_session, "1021", "Synthetic Checking")
    savings = _register(db_session, "1022", "Synthetic Savings")
    general = _account(db_session, "6111", "General Expense", AccountType.EXPENSE)
    scoped = _account(db_session, "6112", "Scoped Expense", AccountType.EXPENSE)
    personal = TxnClass(name="Personal")
    vendor = Vendor(name="Northstar Office")
    db_session.add_all([personal, vendor])
    db_session.commit()
    _create_rule(
        client,
        name="Low priority fallback",
        pattern="NORTHSTAR",
        rule_type="contains",
        match_field="raw",
        direction="any",
        priority=1,
        account_id=general.id,
    )
    high = _create_rule(
        client,
        bank_account_id=checking.id,
        minimum_amount="40.00",
        maximum_amount="50.00",
        account_id=scoped.id,
        vendor_id=vendor.id,
        class_id=personal.id,
        intent="direct_expense",
        posting_route="direct",
        counterparty_role="payee",
        counterparty_resolution="vendor",
        class_resolution="assigned",
    )

    row = _row(
        db_session,
        checking,
        "scoped",
        "-42.10",
        "DEBIT CARD PURCHASE SQ *NORTHSTAR OFFICE 4821",
    )
    proposal = client.post(f"/api/banking/transactions/{row.id}/suggest").json()
    assert proposal["proposal_source"] == "rule"
    assert proposal["intent"] == "direct_expense"
    assert proposal["counter_account_id"] == scoped.id
    assert proposal["vendor_id"] == vendor.id
    assert proposal["class_id"] == personal.id
    assert f"Rule {high['id']}" in proposal["rationale"]

    wrong_register = _row(db_session, savings, "register", "-42.10", "NORTHSTAR OFFICE")
    other = client.post(f"/api/banking/transactions/{wrong_register.id}/suggest").json()
    assert other["counter_account_id"] == general.id
    assert f"Rule {high['id']}" not in other["rationale"]

    out_of_range = _row(db_session, checking, "range", "-60.00", "NORTHSTAR OFFICE")
    outside = client.post(f"/api/banking/transactions/{out_of_range.id}/suggest").json()
    assert outside["counter_account_id"] == general.id


def test_apply_creates_proposal_but_never_approval_or_ledger_post(client, db_session):
    register = _register(db_session, "1031", "Synthetic Checking")
    expense = _account(db_session, "6121", "Office Expense", AccountType.EXPENSE)
    personal = TxnClass(name="Personal")
    vendor = Vendor(name="Northstar Office")
    db_session.add_all([personal, vendor])
    db_session.commit()
    rule = _create_rule(
        client,
        bank_account_id=register.id,
        account_id=expense.id,
        vendor_id=vendor.id,
        class_id=personal.id,
        intent="direct_expense",
        posting_route="direct",
        counterparty_role="payee",
        counterparty_resolution="vendor",
        class_resolution="assigned",
    )
    row = _row(db_session, register, "apply", "-44.00", "NORTHSTAR OFFICE 9911")

    applied = client.post("/api/bank-rules/apply")
    assert applied.status_code == 200, applied.text
    assert applied.json() == {"matched": 1, "proposed": 1, "total_unmatched": 1}
    db_session.expire_all()
    stored = db_session.get(BankTransaction, row.id)
    proposal = db_session.query(BankTransactionProposal).one()
    assert stored.match_status == "auto"
    assert stored.category_account_id == expense.id
    assert stored.transaction_id is None
    assert proposal.status == "proposed"
    assert proposal.proposal_source == "rule"
    assert proposal.created_by == f"rule:{rule['id']}"
    assert db_session.query(Transaction).count() == 0


def test_equal_priority_uses_oldest_rule_and_applies_customer(client, db_session):
    register = _register(db_session, "1032", "Synthetic Revenue Checking")
    first_income = _account(db_session, "4021", "First Income", AccountType.INCOME)
    second_income = _account(db_session, "4022", "Second Income", AccountType.INCOME)
    business = TxnClass(name="Sch C - Synthetic")
    customer = Customer(name="Cedar Workshop")
    db_session.add_all([business, customer])
    db_session.commit()
    common = {
        "pattern": "CEDAR WORKSHOP",
        "rule_type": "contains",
        "match_field": "normalized",
        "direction": "deposit",
        "customer_id": customer.id,
        "class_id": business.id,
        "intent": "direct_income",
        "posting_route": "direct",
        "counterparty_role": "payer",
        "counterparty_resolution": "customer",
        "class_resolution": "assigned",
        "priority": 50,
    }
    first = _create_rule(
        client, name="First equal-priority rule", account_id=first_income.id, **common
    )
    _create_rule(
        client, name="Second equal-priority rule", account_id=second_income.id, **common
    )
    row = _row(db_session, register, "tie", "125.00", "SQ *CEDAR WORKSHOP 4488")

    proposal = client.post(f"/api/banking/transactions/{row.id}/suggest").json()
    assert proposal["counter_account_id"] == first_income.id
    assert proposal["customer_id"] == customer.id
    assert proposal["class_id"] == business.id
    assert f"Rule {first['id']}" in proposal["rationale"]


def test_approved_proposal_offers_draft_without_creating_rule(client, db_session):
    register = _register(db_session, "1041", "Synthetic Checking")
    expense = _account(db_session, "6131", "Office Expense", AccountType.EXPENSE)
    personal = TxnClass(name="Personal")
    db_session.add(personal)
    db_session.commit()
    row = _row(
        db_session,
        register,
        "draft",
        "-48.00",
        "DEBIT CARD PURCHASE SQ *CEDAR WORKSHOP 4821",
    )
    created = client.post(
        f"/api/banking/transactions/{row.id}/proposals",
        json={
            "intent": "direct_expense",
            "posting_route": "direct",
            "normalized_counterparty": "Cedar Workshop",
            "counterparty_role": "payee",
            "counterparty_resolution": "text_only",
            "counter_account_id": expense.id,
            "class_resolution": "assigned",
            "class_id": personal.id,
        },
    ).json()
    assert (
        client.post(f"/api/banking/proposals/{created['id']}/approve").status_code
        == 200
    )

    draft = client.get(f"/api/bank-rules/proposal-draft/{created['id']}")
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert body["pattern"] == "CEDAR WORKSHOP"
    assert body["match_field"] == "normalized"
    assert body["bank_account_id"] == register.id
    assert body["direction"] == "withdrawal"
    assert body["intent"] == "direct_expense"
    assert db_session.query(BankRule).count() == 0

    saved = client.post("/api/bank-rules", json=body)
    assert saved.status_code == 201, saved.text
    assert db_session.query(BankRule).count() == 1


def test_rule_validation_rejects_unsafe_direction_and_missing_references(client):
    unsafe = client.post(
        "/api/bank-rules",
        json={
            "name": "Unsafe expense",
            "pattern": "SYNTHETIC",
            "direction": "any",
            "intent": "direct_expense",
            "posting_route": "direct",
        },
    )
    assert unsafe.status_code == 422
    missing = client.post(
        "/api/bank-rules",
        json={
            "name": "Missing account",
            "pattern": "SYNTHETIC",
            "account_id": 999999,
        },
    )
    assert missing.status_code == 400


def test_rule_ui_exposes_scopes_decisions_and_explicit_draft_action():
    root = Path(__file__).resolve().parent.parent
    rules_js = (root / "app/static/js/bank_rules.js").read_text()
    review_js = (root / "app/static/js/bank_review.js").read_text()
    for field in (
        "match_field",
        "bank_account_id",
        "direction",
        "minimum_amount",
        "maximum_amount",
        "customer_id",
        "vendor_id",
        "class_resolution",
    ):
        assert f'name="{field}"' in rules_js
    assert (
        "Rules propose reviewed accounting mappings; they never approve or post"
        in rules_js
    )
    assert "data-bank-rule-draft" in review_js
    assert "/bank-rules/proposal-draft/" in review_js


def test_phase_five_migration_preserves_legacy_rules(tmp_path):
    import sqlite3

    from alembic import command
    from alembic.config import Config

    database = tmp_path / "expanded-bank-rules.db"
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.attributes["database_url"] = "sqlite:///" + database.as_posix()
    command.upgrade(config, "91f5a4c8d2e7")
    connection = sqlite3.connect(database)
    connection.execute(
        "insert into bank_rules (name, pattern, rule_type, priority, is_active) "
        "values ('Legacy', 'LEGACY SHOP', 'contains', 0, 1)"
    )
    connection.commit()
    connection.close()

    command.upgrade(config, "head")
    connection = sqlite3.connect(database)
    row = connection.execute(
        "select match_field, direction, customer_id from bank_rules where name='Legacy'"
    ).fetchone()
    connection.close()
    assert row == ("raw", "any", None)

    command.downgrade(config, "91f5a4c8d2e7")
    connection = sqlite3.connect(database)
    columns = {item[1] for item in connection.execute("pragma table_info(bank_rules)")}
    connection.close()
    assert "match_field" not in columns
    assert "bank_account_id" not in columns
