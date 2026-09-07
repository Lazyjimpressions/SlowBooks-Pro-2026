"""Bank-register balance updates shared by every import path."""

from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.models.banking import BankAccount


def add_imported_amounts(
    db: Session, bank_account_id: int, amounts: Iterable[Decimal]
) -> Decimal:
    """Add newly imported amounts to a register balance atomically.

    Importers must pass only rows that survived deduplication. This preserves
    any opening balance already stored on the register and makes a repeated
    import a no-op. The update participates in the caller's transaction so
    rows and their balance movement commit or roll back together.
    """
    delta = sum((Decimal(str(amount)) for amount in amounts), Decimal("0"))
    if delta == 0:
        return delta

    result = db.execute(
        update(BankAccount)
        .where(BankAccount.id == bank_account_id)
        .values(balance=func.coalesce(BankAccount.balance, 0) + delta)
    )
    if result.rowcount != 1:
        raise ValueError(f"Bank account {bank_account_id} not found")
    return delta
