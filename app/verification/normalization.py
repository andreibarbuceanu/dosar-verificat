"""Conservative normalizers for Romanian business data."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


_SPACES = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_LEGAL_FORMS = {
    "societate cu raspundere limitata": "srl",
    "societatea cu raspundere limitata": "srl",
    "s r l": "srl",
    "s a": "sa",
}
_CURRENCIES = {
    "RON": "RON",
    "LEI": "RON",
    "LEU": "RON",
    "EURO": "EUR",
    "EUR": "EUR",
    "USD": "USD",
}
_MONTHS = {
    "ianuarie": 1,
    "februarie": 2,
    "martie": 3,
    "aprilie": 4,
    "mai": 5,
    "iunie": 6,
    "iulie": 7,
    "august": 8,
    "septembrie": 9,
    "octombrie": 10,
    "noiembrie": 11,
    "decembrie": 12,
}
_NAME_TITLES = {"dl", "dna", "domnul", "doamna", "administrator", "director"}


def fold_text(value: Any) -> str | None:
    """Case-fold text, remove diacritics/punctuation, and collapse spaces."""

    if not isinstance(value, str) or not value.strip():
        return None
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = _NON_ALNUM.sub(" ", ascii_text).strip()
    return _SPACES.sub(" ", normalized) or None


def normalize_cui(value: Any) -> str | None:
    """Normalize a Romanian CUI, accepting an optional ``RO`` prefix."""

    if isinstance(value, bool) or value is None:
        return None
    compact = re.sub(r"[\s.\-/]", "", str(value)).upper()
    if compact.startswith("RO"):
        compact = compact[2:]
    if not compact.isdigit() or not 2 <= len(compact) <= 10:
        return None
    return compact.lstrip("0") or "0"


def normalize_company_name(value: Any) -> str | None:
    """Normalize spelling and common Romanian legal-form variants."""

    normalized = fold_text(value)
    if normalized is None:
        return None
    for phrase, replacement in _LEGAL_FORMS.items():
        normalized = re.sub(rf"\b{re.escape(phrase)}\b", replacement, normalized)
    return _SPACES.sub(" ", normalized).strip()


def normalize_person_name(value: Any) -> str | None:
    """Normalize a person's name and tolerate family/given-name order."""

    normalized = fold_text(value)
    if normalized is None:
        return None
    tokens = [token for token in normalized.split() if token not in _NAME_TITLES]
    return " ".join(sorted(tokens)) or None


def normalize_currency(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return _CURRENCIES.get(value.strip().upper())


def normalize_money(value: Any) -> Decimal | None:
    """Parse Romanian/international money formatting without guessing units."""

    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip().upper().replace("\u00a0", " ")
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"\b(RON|LEI|LEU|EUR|EURO|USD)\b", "", text).strip(" ()")
    text = text.replace(" ", "")

    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", text):
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", text):
        text = text.replace(",", "")
    elif re.fullmatch(r"-?\d+(,\d+)?", text):
        text = text.replace(",", ".")
    elif not re.fullmatch(r"-?\d+(\.\d+)?", text):
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    return -amount if negative and amount > 0 else amount


def normalize_year(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        year = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return year if 1900 <= year <= 2100 else None


def normalize_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-zĂÂÎȘŞȚŢăâîșşțţ]+)\s+(\d{4})", text)
    if match:
        month = _MONTHS.get(fold_text(match.group(2)) or "")
        if month:
            try:
                return date(int(match.group(3)), month, int(match.group(1)))
            except ValueError:
                return None
    return None
