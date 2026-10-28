"""Deterministic prompt-injection detector. Runs on every page, model or no model (R15)."""
from __future__ import annotations

import re

from .normalize import fold

_PATTERNS = [re.compile(p) for p in (
    r"\bignor\w*\b.{0,40}\b(rules?|instructions?|prompt|reguli\w*|instructiuni\w*|verificari\w*)\b",
    r"\b(disregard|override|forget)\b.{0,40}\b(rules?|instructions?|checks?|prompt)\b",
    r"\b(approve|aproba\w*)\b.{0,30}\b(this|acest\w*|aceasta)\b.{0,20}\b(file|application|loan|request|dosar\w*|cerere\w*|credit\w*)\b",
    r"\bsystem prompt\b",
    r"\b(you are|you're|as) an? (ai|language model|llm|assistant)\b",
    r"\b(esti|sunteti) (un )?(asistent|model|ai|ia)\b",
    r"\bset\b.{0,30}\b(turnover|revenue|profit|value|field|cifra\w*)\b.{0,20}\bto\b",
)]


def detect_injection(pages: list[str]) -> list[dict]:
    """Lines that address an AI. [{page, text}] with the line exactly as on the page."""
    hits = []
    for number, text in enumerate(pages, start=1):
        for line in (text or "").splitlines():
            line = line.strip()
            folded = fold(line)
            if line and any(p.search(folded) for p in _PATTERNS):
                hits.append({"page": number, "text": line[:300]})
    return hits
