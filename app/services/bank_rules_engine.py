"""Deterministic Bank Rule matching and proposal creation."""

import logging
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.banking import BankTransaction, BankTransactionProposal
from app.services.bank_normalization import normalize_bank_text

logger = logging.getLogger(__name__)

ACTIVE_PROPOSAL_STATUSES = ("proposed", "approved")


def _direction(txn: BankTransaction) -> str:
    return "deposit" if Decimal(str(txn.amount)) > 0 else "withdrawal"


def _text_matches(rule, txn_or_payee: BankTransaction | str) -> bool:
    pattern = (rule.pattern or "").strip()
    if not pattern:
        return False
    if rule.match_field == "normalized":
        normalized = (
            normalize_bank_text(txn_or_payee.payee, txn_or_payee.description)
            if isinstance(txn_or_payee, BankTransaction)
            else normalize_bank_text(txn_or_payee, None)
        )
        candidates = [normalized.normalized_key]
        pattern = normalize_bank_text(pattern, None).normalized_key
    elif isinstance(txn_or_payee, BankTransaction):
        candidates = [txn_or_payee.payee or "", txn_or_payee.description or ""]
    else:
        candidates = [txn_or_payee or ""]

    pattern = pattern.casefold()
    candidates = [candidate.casefold() for candidate in candidates]
    if not pattern:
        return False
    if rule.rule_type == "contains":
        return any(pattern in candidate for candidate in candidates)
    if rule.rule_type == "starts_with":
        return any(candidate.startswith(pattern) for candidate in candidates)
    if rule.rule_type == "exact":
        return any(candidate == pattern for candidate in candidates)
    return False


def rule_matches(rule, txn_or_payee: BankTransaction | str) -> bool:
    """Match text plus optional register, direction, and absolute amount scope."""
    if isinstance(txn_or_payee, BankTransaction):
        txn = txn_or_payee
        if (
            rule.bank_account_id is not None
            and rule.bank_account_id != txn.bank_account_id
        ):
            return False
        if rule.direction != "any" and rule.direction != _direction(txn):
            return False
        amount = abs(Decimal(str(txn.amount)))
        if rule.minimum_amount is not None and amount < Decimal(rule.minimum_amount):
            return False
        if rule.maximum_amount is not None and amount > Decimal(rule.maximum_amount):
            return False
    return _text_matches(rule, txn_or_payee)


def _active_rules(db: Session):
    from app.models.bank_rules import BankRule

    return (
        db.query(BankRule)
        .filter(BankRule.is_active)
        .order_by(BankRule.priority.desc(), BankRule.id)
        .all()
    )


def find_matching_rule(db: Session, txn_or_payee: BankTransaction | str):
    """Return the highest-priority active rule; oldest ID wins a tie."""
    return next(
        (rule for rule in _active_rules(db) if rule_matches(rule, txn_or_payee)),
        None,
    )


def _has_active_proposal(db: Session, txn_id: int) -> bool:
    return (
        db.query(BankTransactionProposal.id)
        .filter(
            BankTransactionProposal.bank_transaction_id == txn_id,
            BankTransactionProposal.status.in_(ACTIVE_PROPOSAL_STATUSES),
        )
        .first()
        is not None
    )


def _create_rule_proposal(db: Session, txn: BankTransaction, rule) -> bool:
    if txn.transaction_id is not None or _has_active_proposal(db, txn.id):
        return False
    # Local import prevents a module cycle: classification itself uses the
    # matcher, while batch/import application persists its returned contract.
    from app.services.bank_classification import build_bank_suggestion

    values = build_bank_suggestion(db, txn)
    if values.get("proposal_source") != "rule":
        return False
    revision = (
        db.query(func.max(BankTransactionProposal.revision))
        .filter(BankTransactionProposal.bank_transaction_id == txn.id)
        .scalar()
        or 0
    ) + 1
    db.add(
        BankTransactionProposal(
            bank_transaction_id=txn.id,
            revision=revision,
            status="proposed",
            created_by=f"rule:{rule.id}",
            **values,
        )
    )
    return True


def apply_rules_to_scope(
    db: Session, bank_account_id: int | None = None
) -> dict[str, int]:
    """Apply legacy category hints and create non-posting review proposals."""
    query = db.query(BankTransaction).filter(
        BankTransaction.match_status == "unmatched"
    )
    if bank_account_id is not None:
        query = query.filter(BankTransaction.bank_account_id == bank_account_id)
    unmatched = query.all()
    matched = 0
    proposed = 0
    rules = _active_rules(db)
    for txn in unmatched:
        rule = next((item for item in rules if rule_matches(item, txn)), None)
        if rule is None:
            continue
        if rule.account_id is not None:
            txn.category_account_id = rule.account_id
        txn.match_status = "auto"
        matched += 1
        if _create_rule_proposal(db, txn, rule):
            proposed += 1
    if matched:
        db.commit()
    return {"matched": matched, "proposed": proposed, "total_unmatched": len(unmatched)}


def apply_bank_rules(db: Session, bank_account_id: int) -> int:
    """Compatibility wrapper used by OFX and CSV importers."""
    return apply_rules_to_scope(db, bank_account_id)["matched"]
