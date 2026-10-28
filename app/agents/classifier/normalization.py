"""Normalization helpers for Romanian OCR/extracted text."""

import re
import unicodedata


_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str) -> str:
    """Normalize case, Romanian diacritics, punctuation and whitespace."""

    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return _NON_ALPHANUMERIC.sub(" ", without_marks).strip()
