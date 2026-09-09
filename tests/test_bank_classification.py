"""Deterministic bank normalization and proposal suggestion tests."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.accounts import Account, AccountType
from app.models.bank_rules import BankRule
from app.models.banking import BankAccount, BankTransaction, BankTransactionProposal
from app.models.bills import Bill, BillStatus
from app.models.classes import TxnClass
from app.models.contacts import Customer, Vendor
from app.models.invoices import Invoice, InvoiceStatus
from app.models.transactions import Transaction
from app.services.bank_normalization import normalize_bank_text


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


def _register(db, name="Synthetic Checking", number="1019"):
    account = _account(db, number, name, AccountType.ASSET)
    register = BankAccount(name=name, account=account, balance=Decimal("0"))
    db.add(register)
    db.flush()
    return register


def _row(
    db,
    register,
    *,
    amount,
    payee,
    description="Synthetic imported description",
    row_date=date(2026, 6, 15),
    import_id=None,
):
    row = BankTransaction(
        bank_account=register,
        date=row_date,
        amount=Decimal(amount),
        payee=payee,
        description=description,
        import_id=import_id or f"synthetic-{register.id}-{payee}-{amount}",
        import_source="ofx",
        match_status="unmatched",
    )
    db.add(row)
    db.commit()
    return row


def test_noisy_descriptions_normalize_together_without_mutating_source():
    first = "DEBIT CARD PURCHASE SQ *CEDAR WORKSHOP 4821"
    second = "PURCHASE AUTHORIZED ON 09/01 TST*CEDAR WORKSHOP CARD 4821"
    first_result = normalize_bank_text(first, None)
    second_result = normalize_bank_text(second, None)

    assert first_result.normalized_key == "CEDAR WORKSHOP"
    assert second_result.normalized_key == "CEDAR WORKSHOP"
    assert first == "DEBIT CARD PURCHASE SQ *CEDAR WORKSHOP 4821"
    assert second == "PURCHASE AUTHORIZED ON 09/01 TST*CEDAR WORKSHOP CARD 4821"
    assert first_result.normalizer_version == "bank-text-v1"

    located = normalize_bank_text("CEDAR WORKSHOP | CHICAGO, IL 60601", None)
    referenced = normalize_bank_text("CEDAR WORKSHOP INV-1001", None)
    assert located.normalized_key == "CEDAR WORKSHOP"
    assert referenced.normalized_key == "CEDAR WORKSHOP"
    assert "INV-1001" in referenced.reference_tokens


def test_reviewed_alias_populates_contact_account_and_class_proposal(
    client, db_session
):
    register = _register(db_session)
    expense = _account(db_session, "6119", "Synthetic Supplies", AccountType.EXPENSE)
    txn_class = TxnClass(name="Sch C - Synthetic")
    vendor = Vendor(name="Cedar Workshop")
    db_session.add_all([txn_class, vendor])
    db_session.commit()
    row = _row(
        db_session,
        register,
        amount="-64.20",
        payee="DEBIT CARD PURCHASE SQ *CEDAR WORKSHOP 4821",
    )
    raw_payee = row.payee
    raw_description = row.description

    alias = client.post(
        "/api/banking/counterparty-aliases",
        json={
            "pattern": "SQ *CEDAR WORKSHOP 9999",
            "canonical_name": "Cedar Workshop",
            "direction": "withdrawal",
            "counterparty_role": "payee",
            "vendor_id": vendor.id,
            "default_account_id": expense.id,
            "default_class_id": txn_class.id,
        },
    )
    assert alias.status_code == 201, alias.text
    assert alias.json()["normalized_pattern"] == "CEDAR WORKSHOP"

    response = client.post(f"/api/banking/transactions/{row.id}/suggest")
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["intent"] == "direct_expense"
    assert proposal["posting_route"] == "direct"
    assert proposal["vendor_id"] == vendor.id
    assert proposal["counter_account_id"] == expense.id
    assert proposal["class_resolution"] == "assigned"
    assert proposal["class_id"] == txn_class.id
    assert proposal["normalizer_version"] == "bank-text-v1"
    assert proposal["confidence_components"][0]["name"] == "reviewed_alias"

    db_session.expire_all()
    stored = db_session.get(BankTransaction, row.id)
    assert stored.payee == raw_payee
    assert stored.description == raw_description
    assert stored.category_account_id is None
    assert stored.transaction_id is None
    assert db_session.query(Transaction).count() == 0

    deactivated = client.delete(
        f"/api/banking/counterparty-aliases/{alias.json()['id']}"
    )
    assert deactivated.status_code == 200
    replacement = client.post(
        "/api/banking/counterparty-aliases",
        json={
            "pattern": "SQ *CEDAR WORKSHOP 9999",
            "canonical_name": "Cedar Workshop",
            "direction": "withdrawal",
            "counterparty_role": "payee",
            "vendor_id": vendor.id,
        },
    )
    assert replacement.status_code == 201, replacement.text


def test_exact_contact_and_bank_rule_suggest_direct_expense(client, db_session):
    register = _register(db_session)
    expense = _account(db_session, "6129", "Office Expense", AccountType.EXPENSE)
    vendor = Vendor(name="Northstar Office")
    db_session.add(vendor)
    db_session.flush()
    db_session.add(
        BankRule(
            name="Northstar synthetic rule",
            pattern="NORTHSTAR OFFICE",
            account_id=expense.id,
            vendor_id=vendor.id,
            rule_type="contains",
            priority=100,
            is_active=True,
        )
    )
    db_session.commit()
    row = _row(
        db_session,
        register,
        amount="-42.10",
        payee="NORTHSTAR OFFICE #104",
    )

    proposal = client.post(f"/api/banking/transactions/{row.id}/suggest").json()
    assert proposal["intent"] == "direct_expense"
    assert proposal["vendor_id"] == vendor.id
    assert proposal["counter_account_id"] == expense.id
    names = {item["name"] for item in proposal["confidence_components"]}
    assert {"bank_rule"}.issubset(names)


def test_similar_contact_names_do_not_merge(client, db_session):
    register = _register(db_session)
    db_session.add_all(
        [Vendor(name="Cedar Workshop"), Vendor(name="Cedar Workshop East")]
    )
    db_session.commit()
    row = _row(
        db_session,
        register,
        amount="-15.00",
        payee="CEDAR WORKSHOP WEST",
    )

    proposal = client.post(f"/api/banking/transactions/{row.id}/suggest").json()
    assert proposal["counterparty_resolution"] == "unresolved"
    assert proposal["vendor_id"] is None


def test_direction_prevents_expense_account_from_classifying_deposit(
    client, db_session
):
    register = _register(db_session)
    expense = _account(db_session, "6139", "Synthetic Expense", AccountType.EXPENSE)
    db_session.add(
        BankRule(
            name="Direction guard rule",
            pattern="SYNTHETIC REFUND",
            account_id=expense.id,
            rule_type="contains",
            priority=100,
            is_active=True,
        )
    )
    db_session.commit()
    row = _row(
        db_session,
        register,
        amount="20.00",
        payee="SYNTHETIC REFUND",
    )

    proposal = client.post(f"/api/banking/transactions/{row.id}/suggest").json()
    assert proposal["counter_account_id"] == expense.id
    assert proposal["intent"] == "unknown"
    assert proposal["posting_route"] == "hold"


def test_unique_equal_opposite_linked_rows_suggest_transfer(client, db_session):
    checking = _register(db_session, "Synthetic Checking", "1019")
    savings = _register(db_session, "Synthetic Savings", "1029")
    outgoing = _row(
        db_session,
        checking,
        amount="-500.00",
        payee="ONLINE TRANSFER TO SAVINGS",
        row_date=date(2026, 6, 15),
    )
    incoming = _row(
        db_session,
        savings,
        amount="500.00",
        payee="ONLINE TRANSFER FROM CHECKING",
        row_date=date(2026, 6, 16),
    )

    proposal = client.post(f"/api/banking/transactions/{outgoing.id}/suggest").json()
    assert proposal["intent"] == "transfer"
    assert proposal["posting_route"] == "transfer"
    assert proposal["paired_bank_transaction_id"] == incoming.id
    assert proposal["counterparty_resolution"] == "not_applicable"
    assert proposal["confidence"] == "0.9500"


def test_open_invoice_reference_forces_customer_payment_route(client, db_session):
    register = _register(db_session)
    customer = Customer(name="Cedar Workshop")
    db_session.add(customer)
    db_session.flush()
    invoice = Invoice(
        invoice_number="INV-1001",
        customer=customer,
        status=InvoiceStatus.SENT,
        date=date(2026, 6, 1),
        total=Decimal("125.00"),
        balance_due=Decimal("125.00"),
    )
    db_session.add(invoice)
    db_session.commit()
    row = _row(
        db_session,
        register,
        amount="125.00",
        payee="MOBILE DEPOSIT INV-1001",
    )

    proposal = client.post(f"/api/banking/transactions/{row.id}/suggest").json()
    assert proposal["intent"] == "customer_payment"
    assert proposal["posting_route"] == "customer_payment"
    assert proposal["invoice_id"] == invoice.id
    assert proposal["customer_id"] == customer.id
    assert db_session.query(Transaction).count() == 0


def test_open_bill_reference_forces_bill_payment_route(client, db_session):
    register = _register(db_session)
    vendor = Vendor(name="Northstar Office")
    db_session.add(vendor)
    db_session.flush()
    bill = Bill(
        bill_number="BILL-55",
        vendor=vendor,
        status=BillStatus.UNPAID,
        date=date(2026, 6, 1),
        total=Decimal("84.00"),
        balance_due=Decimal("84.00"),
    )
    db_session.add(bill)
    db_session.commit()
    row = _row(
        db_session,
        register,
        amount="-84.00",
        payee="ACH DEBIT BILL-55",
    )

    proposal = client.post(f"/api/banking/transactions/{row.id}/suggest").json()
    assert proposal["intent"] == "bill_payment"
    assert proposal["posting_route"] == "bill_payment"
    assert proposal["bill_id"] == bill.id
    assert proposal["vendor_id"] == vendor.id
    assert db_session.query(Transaction).count() == 0


def test_prior_reviewed_decision_is_reused_by_direction(client, db_session):
    register = _register(db_session)
    income = _account(db_session, "4119", "Synthetic Revenue", AccountType.INCOME)
    prior_row = _row(
        db_session,
        register,
        amount="90.00",
        payee="CEDAR WORKSHOP 1111",
        row_date=date(2026, 5, 15),
    )
    prior = BankTransactionProposal(
        bank_transaction_id=prior_row.id,
        revision=1,
        status="approved",
        intent="direct_income",
        posting_route="direct",
        normalized_counterparty="Cedar Workshop",
        normalized_counterparty_key="CEDAR WORKSHOP",
        counterparty_role="payer",
        counterparty_resolution="text_only",
        counter_account_id=income.id,
        class_resolution="personal_no_class",
        proposal_source="human",
        confidence=Decimal("1.0000"),
        created_by="reviewer",
    )
    db_session.add(prior)
    db_session.commit()
    row = _row(
        db_session,
        register,
        amount="105.00",
        payee="CEDAR WORKSHOP 2222",
        row_date=date(2026, 6, 15),
    )

    proposal = client.post(f"/api/banking/transactions/{row.id}/suggest").json()
    assert proposal["intent"] == "direct_income"
    assert proposal["counter_account_id"] == income.id
    assert proposal["class_resolution"] == "personal_no_class"
    assert proposal["confidence_components"][0]["name"] == "prior_reviewed_decision"


def test_phase_two_migration_round_trip(tmp_path):
    import sqlite3

    from alembic import command
    from alembic.config import Config

    database = tmp_path / "classification-migration.db"
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
    tables = {
        row[0]
        for row in connection.execute(
            "select name from sqlite_master where type = 'table'"
        )
    }
    global_alias_index = connection.execute(
        "select sql from sqlite_master where type = 'index' "
        "and name = 'uq_bank_alias_global'"
    ).fetchone()[0]
    connection.close()
    assert "normalized_counterparty_key" in proposal_columns
    assert "confidence_components" in proposal_columns
    assert "bank_counterparty_aliases" in tables
    assert "is_active = true" in global_alias_index

    command.downgrade(config, "f8a9b0c1d2e3")
    connection = sqlite3.connect(database)
    proposal_columns = {
        row[1]
        for row in connection.execute("pragma table_info(bank_transaction_proposals)")
    }
    tables = {
        row[0]
        for row in connection.execute(
            "select name from sqlite_master where type = 'table'"
        )
    }
    connection.close()
    assert "normalized_counterparty_key" not in proposal_columns
    assert "confidence_components" not in proposal_columns
    assert "bank_counterparty_aliases" not in tables
