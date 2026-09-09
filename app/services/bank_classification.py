"""Deterministic, inspectable suggestions for imported bank transactions."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.accounts import Account, AccountType
from app.models.banking import (
    BankAccount,
    BankCounterpartyAlias,
    BankTransaction,
    BankTransactionProposal,
)
from app.models.bills import Bill, BillStatus
from app.models.contacts import Customer, Vendor
from app.models.invoices import Invoice, InvoiceStatus
from app.services.bank_normalization import normalize_bank_text, normalize_contact_name
from app.services.bank_rules_engine import find_matching_rule

ACTIVE_DOCUMENT_DAYS = 180


def _component(components: list[dict], name: str, score: str, detail: str) -> None:
    components.append({"name": name, "score": score, "detail": detail})


def _direction(txn: BankTransaction) -> str:
    return "deposit" if Decimal(str(txn.amount)) > 0 else "withdrawal"


def _matching_alias(
    db: Session, txn: BankTransaction, normalized_key: str
) -> BankCounterpartyAlias | None:
    direction = _direction(txn)
    aliases = (
        db.query(BankCounterpartyAlias)
        .filter(
            BankCounterpartyAlias.is_active,
            BankCounterpartyAlias.normalized_pattern == normalized_key,
            BankCounterpartyAlias.direction.in_(("any", direction)),
            or_(
                BankCounterpartyAlias.bank_account_id.is_(None),
                BankCounterpartyAlias.bank_account_id == txn.bank_account_id,
            ),
        )
        .all()
    )
    if not aliases:
        return None
    aliases.sort(
        key=lambda alias: (
            alias.bank_account_id == txn.bank_account_id,
            alias.direction == direction,
            alias.id,
        ),
        reverse=True,
    )
    return aliases[0]


def _prior_decision(
    db: Session, txn: BankTransaction, normalized_key: str
) -> BankTransactionProposal | None:
    if not normalized_key:
        return None
    direction_filter = (
        BankTransaction.amount > 0
        if Decimal(str(txn.amount)) > 0
        else BankTransaction.amount < 0
    )
    return (
        db.query(BankTransactionProposal)
        .join(
            BankTransaction,
            BankTransaction.id == BankTransactionProposal.bank_transaction_id,
        )
        .filter(
            BankTransactionProposal.normalized_counterparty_key == normalized_key,
            BankTransactionProposal.status.in_(("approved", "posted")),
            BankTransactionProposal.bank_transaction_id != txn.id,
            direction_filter,
        )
        .order_by(
            BankTransactionProposal.created_at.desc(),
            BankTransactionProposal.id.desc(),
        )
        .first()
    )


def _exact_contact_match(db: Session, normalized_key: str):
    if not normalized_key:
        return None
    matches: list[tuple[str, Customer | Vendor]] = []
    for customer in db.query(Customer).filter(Customer.is_active).all():
        if normalize_contact_name(customer.name) == normalized_key:
            matches.append(("customer", customer))
    for vendor in db.query(Vendor).filter(Vendor.is_active).all():
        if normalize_contact_name(vendor.name) == normalized_key:
            matches.append(("vendor", vendor))
    return matches[0] if len(matches) == 1 else None


def _transfer_candidate(db: Session, txn: BankTransaction) -> BankTransaction | None:
    current_register = db.get(BankAccount, txn.bank_account_id)
    if (
        current_register is None
        or current_register.account_id is None
        or Decimal(str(txn.amount)) == 0
    ):
        return None
    earliest = txn.date - timedelta(days=3)
    latest = txn.date + timedelta(days=3)
    active_proposal_exists = (
        db.query(BankTransactionProposal.id)
        .filter(
            BankTransactionProposal.bank_transaction_id == BankTransaction.id,
            BankTransactionProposal.status.in_(("proposed", "approved")),
        )
        .exists()
    )
    candidates = (
        db.query(BankTransaction)
        .join(BankAccount, BankAccount.id == BankTransaction.bank_account_id)
        .filter(
            BankTransaction.id != txn.id,
            BankTransaction.bank_account_id != txn.bank_account_id,
            BankAccount.account_id.is_not(None),
            BankTransaction.transaction_id.is_(None),
            ~active_proposal_exists,
            BankTransaction.date.between(earliest, latest),
            BankTransaction.amount == -Decimal(str(txn.amount)),
        )
        .all()
    )
    return candidates[0] if len(candidates) == 1 else None


def _reference_matches(reference_tokens: tuple[str, ...], *values: str | None) -> bool:
    normalized_values = " ".join((value or "").upper() for value in values)
    return any(
        re.search(rf"(?<![A-Z0-9]){re.escape(token)}(?![A-Z0-9])", normalized_values)
        for token in reference_tokens
    )


def _open_invoice_candidate(
    db: Session,
    txn: BankTransaction,
    customer_id: int | None,
    reference_tokens: tuple[str, ...],
) -> tuple[Invoice | None, bool]:
    if Decimal(str(txn.amount)) <= 0:
        return None, False
    query = db.query(Invoice).filter(
        Invoice.status.in_((InvoiceStatus.SENT, InvoiceStatus.PARTIAL)),
        Invoice.balance_due == Decimal(str(txn.amount)),
        Invoice.date.between(txn.date - timedelta(days=ACTIVE_DOCUMENT_DAYS), txn.date),
    )
    if customer_id is not None:
        query = query.filter(Invoice.customer_id == customer_id)
    candidates = query.all()
    reference_matches = [
        invoice
        for invoice in candidates
        if _reference_matches(
            reference_tokens, invoice.invoice_number, invoice.po_number
        )
    ]
    if len(reference_matches) == 1:
        return reference_matches[0], True
    if customer_id is not None and len(candidates) == 1:
        return candidates[0], False
    return None, False


def _open_bill_candidate(
    db: Session,
    txn: BankTransaction,
    vendor_id: int | None,
    reference_tokens: tuple[str, ...],
) -> tuple[Bill | None, bool]:
    if Decimal(str(txn.amount)) >= 0:
        return None, False
    query = db.query(Bill).filter(
        Bill.status.in_((BillStatus.UNPAID, BillStatus.PARTIAL)),
        Bill.balance_due == abs(Decimal(str(txn.amount))),
        Bill.date.between(txn.date - timedelta(days=ACTIVE_DOCUMENT_DAYS), txn.date),
    )
    if vendor_id is not None:
        query = query.filter(Bill.vendor_id == vendor_id)
    candidates = query.all()
    reference_matches = [
        bill
        for bill in candidates
        if _reference_matches(reference_tokens, bill.bill_number, bill.ref_number)
    ]
    if len(reference_matches) == 1:
        return reference_matches[0], True
    if vendor_id is not None and len(candidates) == 1:
        return candidates[0], False
    return None, False


def build_bank_suggestion(db: Session, txn: BankTransaction) -> dict:
    """Build a proposal payload from deterministic evidence only."""
    normalized = normalize_bank_text(txn.payee, txn.description)
    components: list[dict] = []
    rationale: list[str] = []
    suggestion = {
        "intent": "unknown",
        "posting_route": "hold",
        "normalized_counterparty": normalized.display_name or None,
        "normalized_counterparty_key": normalized.normalized_key or None,
        "counterparty_role": "payer" if _direction(txn) == "deposit" else "payee",
        "counterparty_resolution": "unresolved",
        "customer_id": None,
        "vendor_id": None,
        "counter_account_id": None,
        "class_resolution": "unresolved",
        "class_id": None,
        "invoice_id": None,
        "bill_id": None,
        "paired_bank_transaction_id": None,
        "proposal_source": "deterministic",
        "normalizer_version": normalized.normalizer_version,
    }
    normalization_detail = (
        f"key={normalized.normalized_key or '(empty)'}; "
        f"removed={','.join(normalized.removed_noise) or 'none'}; "
        f"references={','.join(normalized.reference_tokens) or 'none'}"
    )

    transfer = _transfer_candidate(db, txn)
    if transfer is not None:
        suggestion.update(
            intent="transfer",
            posting_route="transfer",
            counterparty_role="not_applicable",
            counterparty_resolution="not_applicable",
            normalized_counterparty=None,
            normalized_counterparty_key=None,
            paired_bank_transaction_id=transfer.id,
        )
        _component(components, "equal_opposite_amount", "0.55", "Exact opposite amount")
        _component(components, "nearby_date", "0.25", "Within three days")
        _component(
            components, "linked_registers", "0.15", "Both registers link to accounts"
        )
        _component(components, "normalization", "0.00", normalization_detail)
        rationale.append(
            f"Unique equal-and-opposite row {transfer.id} in another register"
        )
        suggestion["confidence"] = Decimal("0.9500")
        suggestion["confidence_components"] = components
        suggestion["rationale"] = "; ".join(rationale)
        return suggestion

    alias = _matching_alias(db, txn, normalized.normalized_key)
    if alias is not None:
        suggestion.update(
            normalized_counterparty=alias.canonical_name,
            counterparty_role=alias.counterparty_role,
            customer_id=alias.customer_id,
            vendor_id=alias.vendor_id,
            counter_account_id=alias.default_account_id,
            class_id=alias.default_class_id,
            class_resolution=("assigned" if alias.default_class_id else "unresolved"),
            counterparty_resolution=(
                "customer"
                if alias.customer_id
                else "vendor" if alias.vendor_id else "text_only"
            ),
        )
        _component(components, "reviewed_alias", "0.75", f"Alias {alias.id}")
        rationale.append(f"Matched reviewed alias {alias.id}")

    prior = _prior_decision(db, txn, normalized.normalized_key)
    if prior is not None and alias is None:
        for field in (
            "intent",
            "posting_route",
            "normalized_counterparty",
            "counterparty_role",
            "counterparty_resolution",
            "customer_id",
            "vendor_id",
            "counter_account_id",
            "class_resolution",
            "class_id",
        ):
            suggestion[field] = getattr(prior, field)
        _component(
            components, "prior_reviewed_decision", "0.70", f"Proposal {prior.id}"
        )
        rationale.append(f"Matched prior reviewed proposal {prior.id}")

    rule = find_matching_rule(db, txn.payee or txn.description or "")
    if rule is not None:
        if suggestion["counter_account_id"] is None and rule.account_id is not None:
            suggestion["counter_account_id"] = rule.account_id
        if (
            suggestion["counterparty_resolution"] == "unresolved"
            and rule.vendor_id is not None
        ):
            vendor = db.get(Vendor, rule.vendor_id)
            suggestion["vendor_id"] = rule.vendor_id
            suggestion["counterparty_resolution"] = "vendor"
            if vendor is not None:
                suggestion["normalized_counterparty"] = vendor.name
                suggestion["normalized_counterparty_key"] = normalize_contact_name(
                    vendor.name
                )
        _component(components, "bank_rule", "0.45", f"Rule {rule.id}")
        rationale.append(f"Matched Bank Rule {rule.id}")
    elif (
        suggestion["counter_account_id"] is None
        and txn.match_status == "auto"
        and txn.category_account_id is not None
    ):
        suggestion["counter_account_id"] = txn.category_account_id
        _component(
            components,
            "imported_rule_category",
            "0.35",
            "Category retained from import-time Bank Rule",
        )
        rationale.append("Reused import-time Bank Rule category")

    if suggestion["counterparty_resolution"] == "unresolved":
        contact_match = _exact_contact_match(db, normalized.normalized_key)
        if contact_match is not None:
            kind, contact = contact_match
            suggestion[f"{kind}_id"] = contact.id
            suggestion["counterparty_resolution"] = kind
            suggestion["normalized_counterparty"] = contact.name
            _component(components, "exact_contact_name", "0.35", f"{kind} {contact.id}")
            rationale.append(f"Matched one existing {kind} by normalized exact name")

    customer_id = suggestion["customer_id"]
    invoice, invoice_reference = _open_invoice_candidate(
        db, txn, customer_id, normalized.reference_tokens
    )
    if invoice is not None and (customer_id is not None or invoice_reference):
        suggestion.update(
            intent="customer_payment",
            posting_route="customer_payment",
            invoice_id=invoice.id,
            customer_id=invoice.customer_id,
            vendor_id=None,
            counterparty_resolution="customer",
            normalized_counterparty=invoice.customer.name,
            normalized_counterparty_key=normalize_contact_name(invoice.customer.name),
            class_id=invoice.class_id,
            class_resolution="assigned" if invoice.class_id else "unresolved",
        )
        _component(components, "open_document_amount", "0.35", "Exact invoice balance")
        _component(components, "open_document_contact", "0.25", "Customer resolved")
        if invoice_reference:
            _component(
                components,
                "open_document_reference",
                "0.25",
                "Invoice reference matches",
            )
        _component(
            components, "open_document_date", "0.10", "Invoice is within 180 days"
        )
        rationale.append(
            f"Matched open invoice {invoice.id}; hold for Payment workflow"
        )

    vendor_id = suggestion["vendor_id"]
    bill, bill_reference = _open_bill_candidate(
        db, txn, vendor_id, normalized.reference_tokens
    )
    if bill is not None and (vendor_id is not None or bill_reference):
        suggestion.update(
            intent="bill_payment",
            posting_route="bill_payment",
            bill_id=bill.id,
            vendor_id=bill.vendor_id,
            customer_id=None,
            counterparty_resolution="vendor",
            normalized_counterparty=bill.vendor.name,
            normalized_counterparty_key=normalize_contact_name(bill.vendor.name),
            class_id=bill.class_id,
            class_resolution="assigned" if bill.class_id else "unresolved",
        )
        _component(components, "open_document_amount", "0.35", "Exact bill balance")
        _component(components, "open_document_contact", "0.25", "Vendor resolved")
        if bill_reference:
            _component(
                components, "open_document_reference", "0.25", "Bill reference matches"
            )
        _component(components, "open_document_date", "0.10", "Bill is within 180 days")
        rationale.append(f"Matched open bill {bill.id}; hold for Bill Payment workflow")

    if suggestion["intent"] == "unknown" and suggestion["counter_account_id"]:
        account = db.get(Account, suggestion["counter_account_id"])
        if (
            account.account_type in (AccountType.EXPENSE, AccountType.COGS)
            and Decimal(str(txn.amount)) < 0
        ):
            suggestion.update(intent="direct_expense", posting_route="direct")
        elif (
            account.account_type == AccountType.INCOME and Decimal(str(txn.amount)) > 0
        ):
            suggestion.update(intent="direct_income", posting_route="direct")

    _component(components, "normalization", "0.00", normalization_detail)
    score = min(
        sum((Decimal(component["score"]) for component in components), Decimal("0")),
        Decimal("0.9900"),
    )
    suggestion["confidence"] = score.quantize(Decimal("0.0001"))
    suggestion["confidence_components"] = components
    suggestion["rationale"] = "; ".join(rationale) or "No deterministic match found"
    return suggestion
