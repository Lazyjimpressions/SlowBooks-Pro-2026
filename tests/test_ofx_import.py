"""OFX import balance and retry invariants."""

from datetime import date
from decimal import Decimal

from app.models.banking import BankAccount
from app.services.ofx_import import import_transactions


def test_ofx_import_updates_balance_once_and_preserves_opening(db_session):
    account = BankAccount(
        name="OFX Checking", bank_name="Example Bank", balance=Decimal("25.00")
    )
    db_session.add(account)
    db_session.commit()

    rows = [
        {
            "fitid": "OFX-1",
            "date": date(2026, 9, 1),
            "amount": Decimal("100.00"),
            "payee": "Customer deposit",
            "memo": "Deposit",
        },
        {
            "fitid": "OFX-2",
            "date": date(2026, 9, 2),
            "amount": Decimal("-40.25"),
            "payee": "Supplier",
            "memo": "Purchase",
        },
    ]

    first = import_transactions(db_session, account.id, rows)
    assert first == {"imported": 2, "skipped": 0, "total": 2}
    db_session.refresh(account)
    assert account.balance == Decimal("84.75")

    second = import_transactions(db_session, account.id, rows)
    assert second == {"imported": 0, "skipped": 2, "total": 2}
    db_session.refresh(account)
    assert account.balance == Decimal("84.75")
