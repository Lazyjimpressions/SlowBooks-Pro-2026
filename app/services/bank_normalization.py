"""Deterministic bank-text normalization that never mutates source evidence."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

NORMALIZER_VERSION = "bank-text-v1"

_LEADING_NOISE = re.compile(
    r"^(?:(?:ACH|EFT)\s+(?:CREDIT|DEBIT|PAYMENT)|"
    r"DEBIT\s+CARD(?:\s+PURCHASE)?|CREDIT\s+CARD(?:\s+PURCHASE)?|"
    r"PURCHASE\s+AUTHORIZED\s+ON(?:\s+\d{1,2}/\d{1,2})?|"
    r"RECURRING\s+(?:CARD\s+)?PAYMENT|ONLINE\s+(?:BANKING\s+)?PAYMENT|"
    r"MOBILE\s+(?:PURCHASE|DEPOSIT)|POS(?:\s+DEBIT)?|CHECKCARD|"
    r"SQ|TST)\b[\s*:#-]*",
    re.IGNORECASE,
)
_DATE = re.compile(r"\b(?:\d{1,2}[/-]){1,2}\d{1,4}\b")
_PHONE = re.compile(r"\b(?:\+?1[ .-]?)?(?:\d{3}|\(\d{3}\))[ .-]\d{3}[ .-]\d{4}\b")
_CARD_SUFFIX = re.compile(
    r"\b(?:CARD|ACCT|ACCOUNT|ENDING|XXXX|X{4})\s*[*#:-]*\s*\d{4}\b",
    re.IGNORECASE,
)
_REFERENCE_LABEL = re.compile(
    r"\b(?:REF|REFERENCE|TRACE|CONF|CONFIRMATION|AUTH|AUTHORIZATION|ID)\s*"
    r"[*#:-]*\s*[A-Z0-9-]{4,}\b",
    re.IGNORECASE,
)
_REFERENCE_TOKEN = re.compile(r"\b(?=[A-Z0-9-]{6,}\b)(?=[A-Z0-9-]*\d)[A-Z0-9-]+\b")
_TRAILING_ALNUM_REFERENCE = re.compile(
    r"\s+(?=[A-Z0-9-]{6,}\s*$)(?=[A-Z0-9-]*\d)[A-Z0-9]+-[A-Z0-9-]+\s*$"
)
_TRAILING_NUMBER = re.compile(r"\s+[#*]?\d{3,}\s*$")
_DELIMITED_LOCATION = re.compile(
    r"\s(?:\||/| - )\s*[A-Z .'-]+,?\s+[A-Z]{2}(?:\s+\d{5}(?:-\d{4})?)?\s*$"
)
_STATE_ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\s*$")
_NON_WORD = re.compile(r"[^A-Z0-9&]+")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class NormalizedBankText:
    display_name: str
    normalized_key: str
    tokens: tuple[str, ...]
    reference_tokens: tuple[str, ...]
    removed_noise: tuple[str, ...]
    normalizer_version: str = NORMALIZER_VERSION


def _ascii_upper(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return normalized.encode("ascii", "ignore").decode("ascii").upper()


def _clean(value: str) -> NormalizedBankText:
    working = _ascii_upper(value)
    references = tuple(dict.fromkeys(_REFERENCE_TOKEN.findall(working)))
    removed: list[str] = []

    while True:
        match = _LEADING_NOISE.match(working.strip())
        if not match:
            break
        removed.append(match.group(0).strip())
        working = working.strip()[match.end() :]

    for expression, label in (
        (_PHONE, "phone"),
        (_DATE, "date"),
        (_CARD_SUFFIX, "card_suffix"),
        (_REFERENCE_LABEL, "reference"),
    ):
        updated, count = expression.subn(" ", working)
        if count:
            removed.append(label)
        working = updated

    working, count = _DELIMITED_LOCATION.subn(" ", working)
    if count:
        removed.append("location")
    working, count = _STATE_ZIP.subn(" ", working)
    if count:
        removed.append("state_zip")
    working, count = _TRAILING_ALNUM_REFERENCE.subn(" ", working)
    if count:
        removed.append("trailing_reference")

    working, count = _TRAILING_NUMBER.subn(" ", working)
    if count:
        removed.append("trailing_number")
    working = working.replace("&", " AND ")
    key = _SPACE.sub(" ", _NON_WORD.sub(" ", working)).strip()[:200].rstrip()
    tokens = tuple(key.split())
    display = " ".join(token.capitalize() for token in tokens)
    return NormalizedBankText(
        display_name=display,
        normalized_key=key,
        tokens=tokens,
        reference_tokens=references,
        removed_noise=tuple(removed),
    )


def normalize_bank_text(
    payee: str | None, description: str | None
) -> NormalizedBankText:
    """Return derived matching text while leaving both inputs unchanged.

    Payee is authoritative when it contains a usable name. Description is a
    fallback for institutions that put generic card text in the payee field.
    """
    payee_result = _clean(payee or "")
    description_result = _clean(description or "")
    generic = {"", "PAYMENT", "PURCHASE", "DEPOSIT", "WITHDRAWAL", "TRANSFER"}
    if payee_result.normalized_key not in generic:
        return payee_result
    return NormalizedBankText(
        display_name=description_result.display_name,
        normalized_key=description_result.normalized_key,
        tokens=description_result.tokens,
        reference_tokens=tuple(
            dict.fromkeys(
                payee_result.reference_tokens + description_result.reference_tokens
            )
        ),
        removed_noise=tuple(
            dict.fromkeys(payee_result.removed_noise + description_result.removed_noise)
        ),
    )


def normalize_contact_name(name: str | None) -> str:
    """Normalize a stored contact or alias with the same comparison rules."""
    return _clean(name or "").normalized_key
