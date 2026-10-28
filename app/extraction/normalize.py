"""Text normalization, quote location and value parsing. Deterministic; no model involved.

The model copies raw text; this module decides what that text means and whether it is
really on the page.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal

# Applied per character after NFC. None removes the character.
_CHAR_MAP = {
    # cedilla -> comma below (old Romanian encodings in PDFs)
    "ş": "ș", "Ş": "Ș", "ţ": "ț", "Ţ": "Ț",
    # odd spaces -> space
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", "　": " ",
    # typographic quotes -> ASCII
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "«": '"', "»": '"',
    # dashes and minus -> ASCII hyphen
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
    "−": "-",
    # invisible
    "­": None, "​": None, "‌": None, "‍": None, "﻿": None,
}
_TRANS = str.maketrans(_CHAR_MAP)


def canon(text: str) -> str:
    """NFC, Romanian comma diacritics, ASCII quotes/dashes, collapsed whitespace. Keeps case."""
    text = unicodedata.normalize("NFC", text or "").translate(_TRANS)
    return re.sub(r"\s+", " ", text).strip()


def norm(text: str) -> str:
    """canon() + casefold: the form quotes and pages are compared in."""
    return _norm_with_map(text)[0]


def fold(text: str) -> str:
    """norm() without diacritics, for person names ('Ștefan' == 'Stefan')."""
    decomposed = unicodedata.normalize("NFD", norm(text))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _norm_with_map(text: str) -> tuple[str, list[int]]:
    """Normalized text plus, for each output char, its index in NFC(text)."""
    text = unicodedata.normalize("NFC", text or "")
    out: list[str] = []
    idx: list[int] = []
    prev_space = True  # drops leading whitespace
    for i, ch in enumerate(text):
        for c in ch.translate(_TRANS).casefold():
            if c.isspace():
                if prev_space:
                    continue
                c = " "
            out.append(c)
            idx.append(i)
            prev_space = c == " "
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


class Page:
    """A page's text, normalized once, that quotes can be located in."""

    def __init__(self, text: str):
        self.text = unicodedata.normalize("NFC", text or "")
        self.norm, self._idx = _norm_with_map(self.text)

    def locate(self, quote: str) -> str | None:
        """The exact page substring matching quote after normalization, or None."""
        nq = norm(quote)
        if not nq:
            return None
        pos = self.norm.find(nq)
        if pos < 0:
            return None
        return self.text[self._idx[pos]: self._idx[pos + len(nq) - 1] + 1]


# ---------------------------------------------------------------- numbers

_CURRENCY = re.compile(r"\b(?:lei|ron|eur|euro|usd)\b|%", re.IGNORECASE)
_UNSIGNED = re.compile(r"\d+(?:[.,]\d+)*")


def _valid_groups(groups: list[str]) -> bool:
    return 1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:])


def _parse_unsigned(s: str) -> Decimal | None:
    """'12.400.000', '1.234,56', '12,400,000', '12.5' -> Decimal. Spaces already removed."""
    if not _UNSIGNED.fullmatch(s):
        return None
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thousands = "," if dec == "." else "."
        if s.count(dec) > 1:
            return None
        int_part, frac = s.split(dec)
        groups = int_part.split(thousands)
        if not _valid_groups(groups):
            return None
        return Decimal("".join(groups) + "." + frac)
    sep = "." if "." in s else "," if "," in s else None
    if sep is None:
        return Decimal(s)
    parts = s.split(sep)
    # One separator followed by exactly 3 digits reads as thousands ('12.400' = 12400):
    # Romanian statements write integers that way far more often than 3-decimal values.
    if len(parts) > 2 or (len(parts[1]) == 3 and parts[0] != "0"):
        return Decimal("".join(parts)) if _valid_groups(parts) else None
    return Decimal(parts[0] + "." + parts[1])


def parse_number(raw: str) -> Decimal | None:
    """Romanian or English number, optional 'lei'/'RON'/'%', negative as '-x' or '(x)'."""
    s = _CURRENCY.sub("", canon(raw)).strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1].strip()
    if s.startswith("-"):
        negative, s = not negative, s[1:].strip()
    elif s.startswith("+"):
        s = s[1:].strip()
    value = _parse_unsigned(s.replace(" ", ""))
    if value is None:
        return None
    return -value if negative else value


def to_python(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


_SPACED = re.compile(r"\d{1,3}(?: \d{3})+(?:[.,]\d+)?")


def numbers_in(text: str) -> set[Decimal]:
    """Every number a quote can be read as, with the sign the quote shows."""
    t = canon(text)
    found: set[Decimal] = set()
    for rx in (_UNSIGNED, _SPACED):
        for m in rx.finditer(t):
            value = _parse_unsigned(m.group(0).replace(" ", ""))
            if value is None:
                continue
            before, after = t[: m.start()], t[m.end():]
            if before.rstrip().endswith("(") and after.lstrip().startswith(")"):
                found.add(-value)
            elif before.endswith("-") and not (len(before) > 1 and before[-2].isalnum()):
                found.add(-value)
            elif before.endswith("- "):
                found.update((value, -value))
            else:
                found.add(value)
    return found


# ---------------------------------------------------------------- dates

_MONTHS = {
    "ianuarie": 1, "ian": 1, "january": 1, "jan": 1,
    "februarie": 2, "feb": 2, "february": 2,
    "martie": 3, "mar": 3, "march": 3,
    "aprilie": 4, "apr": 4, "april": 4,
    "mai": 5, "may": 5,
    "iunie": 6, "iun": 6, "june": 6, "jun": 6,
    "iulie": 7, "iul": 7, "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "septembrie": 9, "sep": 9, "sept": 9, "september": 9,
    "octombrie": 10, "oct": 10, "october": 10,
    "noiembrie": 11, "nov": 11, "november": 11,
    "decembrie": 12, "dec": 12, "december": 12,
}
_DMY = re.compile(r"(?<!\d)(\d{1,2}) ?[./-] ?(\d{1,2}) ?[./-] ?(\d{4})(?!\d)")
_YMD = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
_TEXT_DATE = re.compile(r"(?<!\d)(\d{1,2}) (?:de )?([a-z]+)\.? (\d{4})(?!\d)")


def _iso(y: str, m: str | int, d: str) -> str | None:
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def _date_matches(text: str):
    t = fold(text)
    for m in _DMY.finditer(t):
        yield m, _iso(m.group(3), m.group(2), m.group(1))
    for m in _YMD.finditer(t):
        yield m, _iso(m.group(1), m.group(2), m.group(3))
    for m in _TEXT_DATE.finditer(t):
        month = _MONTHS.get(m.group(2))
        yield m, _iso(m.group(3), month, m.group(1)) if month else None


def parse_date(raw: str) -> str | None:
    """'14.10.2026', '14/10/2026', '2026-10-14', '14 octombrie 2026' -> '2026-10-14'."""
    t = fold(raw).rstrip(". ")
    for m, iso in _date_matches(t):
        if iso and m.start() == 0 and m.end() == len(t):
            return iso
    return None


def dates_in(text: str) -> set[str]:
    return {iso for _, iso in _date_matches(text) if iso}


# ---------------------------------------------------------------- other kinds

def parse_year(raw: str) -> int | None:
    t = canon(raw)
    return int(t) if re.fullmatch(r"\d{4}", t) and 1900 <= int(t) <= 2100 else None


def year_in(year: int, text: str) -> bool:
    return re.search(rf"(?<!\d){year}(?!\d)", canon(text)) is not None


_TRUE = {"true", "da", "yes"}
_FALSE = {"false", "nu", "no"}


def parse_bool(raw: str) -> bool | None:
    t = norm(raw)
    return True if t in _TRUE else False if t in _FALSE else None


def parse_code(raw: str) -> str | None:
    """CUI / CAEN: digits only, CUI without the RO prefix."""
    t = re.sub(r"^RO", "", canon(raw).upper()).strip()
    t = re.sub(r"[\s.\-]", "", t)
    return t if re.fullmatch(r"\d+", t) else None


def digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


def parse_text(raw: str) -> str | None:
    return canon(raw) or None


def text_in(value: str, text: str) -> bool:
    return norm(value) in norm(text)
