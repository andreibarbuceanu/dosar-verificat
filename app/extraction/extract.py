"""AI extraction: the model copies, the code decides.

A value without proof never enters the pipeline: every Field returned here has a quote that
is on its page and a parsed value that is in its quote.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from . import normalize as n
from .fields import PERSON_KINDS, FieldSpec, expected_names, fields_for, normalize_type, people_for
from .injection import detect_injection
from .prompt import PROMPT_VERSION, build_prompt, build_schema

Complete = Callable[[str, dict], dict]

QUOTE_NOT_ON_PAGE = "quote_not_on_page"
VALUE_NOT_IN_QUOTE = "value_not_in_quote"
UNPARSEABLE_VALUE = "unparseable_value"
UNKNOWN_FIELD = "unknown_field"
PAGE_OUT_OF_RANGE = "page_out_of_range"


@dataclass
class ExtractionResult:
    doc_id: str
    doc_type: str
    fields: list[dict] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)
    injection_suspected: list[dict] = field(default_factory=list)
    prompt_version: str = PROMPT_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


class _Drop(Exception):
    def __init__(self, reason: str):
        self.reason = reason


def _default_complete() -> Complete:
    try:
        from app.llm import complete
    except ImportError as e:
        raise RuntimeError(
            "app.llm.complete is not available; pass complete= or install the LLM layer"
        ) from e
    return complete


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _items(value: Any) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


class _Extractor:
    def __init__(self, doc_id: str, doc_type: str, pages: list[str]):
        self.doc_id = doc_id
        self.doc_type = doc_type
        self.pages = [n.Page(p) for p in pages]
        self.specs: dict[str, FieldSpec] = {f.name: f for f in fields_for(doc_type)}
        self.kinds = people_for(doc_type)
        self.result = ExtractionResult(doc_id, doc_type)
        self._seen: set[tuple[str, str]] = set()

    # -- evidence

    def _locate(self, page: Any, quote: str) -> tuple[int, str]:
        """(page number, exact page text of the quote). Fixes the page if the quote is on
        exactly one other page."""
        try:
            number = int(page)
        except (TypeError, ValueError):
            raise _Drop(PAGE_OUT_OF_RANGE)
        if not 1 <= number <= len(self.pages):
            raise _Drop(PAGE_OUT_OF_RANGE)
        exact = self.pages[number - 1].locate(quote)
        if exact is not None:
            return number, exact
        others = [
            (i, hit) for i, p in enumerate(self.pages, start=1)
            if i != number and (hit := p.locate(quote)) is not None
        ]
        if len(others) == 1:
            return others[0]
        raise _Drop(QUOTE_NOT_ON_PAGE)

    # -- parsing (value) + proof (value in quote)

    @staticmethod
    def _parse(kind: str, raw: str, quote: str) -> Any:
        if kind in ("money", "int", "percent"):
            number = n.parse_number(raw)
            if number is None or (kind == "int" and number != number.to_integral_value()):
                raise _Drop(UNPARSEABLE_VALUE)
            if number not in n.numbers_in(quote):
                raise _Drop(VALUE_NOT_IN_QUOTE)
            return n.to_python(number)
        if kind == "date":
            iso = n.parse_date(raw)
            if iso is None:
                raise _Drop(UNPARSEABLE_VALUE)
            if iso not in n.dates_in(quote):
                raise _Drop(VALUE_NOT_IN_QUOTE)
            return iso
        if kind == "year":
            year = n.parse_year(raw)
            if year is None:
                raise _Drop(UNPARSEABLE_VALUE)
            if not n.year_in(year, quote):
                raise _Drop(VALUE_NOT_IN_QUOTE)
            return year
        if kind == "bool":
            # A yes/no is a reading of the quoted sentence; the quote is the proof.
            flag = n.parse_bool(raw)
            if flag is None:
                raise _Drop(UNPARSEABLE_VALUE)
            return flag
        if kind == "code":
            code = n.parse_code(raw)
            if code is None:
                raise _Drop(UNPARSEABLE_VALUE)
            if code not in n.digits(quote):
                raise _Drop(VALUE_NOT_IN_QUOTE)
            return code
        text = n.parse_text(raw)
        if text is None:
            raise _Drop(UNPARSEABLE_VALUE)
        if not n.text_in(text, quote):
            raise _Drop(VALUE_NOT_IN_QUOTE)
        return text

    def _person(self, kind: str, item: dict, quote: str) -> dict:
        raw = {k: _str(item.get(k)).strip() for k in PERSON_KINDS[kind]}
        name = n.parse_text(raw["name"])
        if name is None:
            raise _Drop(UNPARSEABLE_VALUE)
        if n.fold(name) not in n.fold(quote):
            raise _Drop(VALUE_NOT_IN_QUOTE)
        value: dict[str, Any] = {"name": name}
        for key in PERSON_KINDS[kind][1:]:
            if not raw[key]:
                value[key] = None
            elif key == "percent":
                value[key] = self._parse("percent", raw[key], quote)
            elif key == "birth_date":
                value[key] = self._parse("date", raw[key], quote)
            else:
                # role / nationality are context, not evidence: kept only if in the quote.
                text = n.parse_text(raw[key])
                value[key] = text if text and n.fold(text) in n.fold(quote) else None
        return value

    # -- intake of model output

    def _keep(self, name: str, value: Any, page: int, quote: str) -> None:
        key = (name, json.dumps(value, sort_keys=True, ensure_ascii=False))
        if key in self._seen:
            return
        self._seen.add(key)
        self.result.fields.append({
            "name": name, "value": value, "doc_id": self.doc_id,
            "page": page, "quote": quote, "verified": True,
        })

    def _drop(self, name: str, value: Any, item: dict, reason: str) -> None:
        self.result.dropped.append({
            "name": name, "value": value, "page": item.get("page"),
            "quote": _str(item.get("quote")), "reason": reason,
        })

    def take_field(self, item: dict) -> None:
        name, raw = _str(item.get("name")), _str(item.get("value"))
        try:
            spec = self.specs.get(name)
            if spec is None:
                raise _Drop(UNKNOWN_FIELD)
            page, quote = self._locate(item.get("page"), _str(item.get("quote")))
            self._keep(name, self._parse(spec.kind, raw, quote), page, quote)
        except _Drop as d:
            self._drop(name, raw, item, d.reason)

    def take_person(self, item: dict) -> None:
        kind = _str(item.get("kind"))
        raw = {k: _str(item.get(k)) for k in ("name", "role", "percent", "birth_date", "nationality")}
        try:
            if kind not in self.kinds:
                raise _Drop(UNKNOWN_FIELD)
            page, quote = self._locate(item.get("page"), _str(item.get("quote")))
            self._keep(kind, self._person(kind, item, quote), page, quote)
        except _Drop as d:
            self._drop(kind, raw, item, d.reason)

    def take_injections(self, reported: list[dict]) -> None:
        """Code-detected lines plus model reports that are really on a page."""
        hits = detect_injection([p.text for p in self.pages])
        for item in reported:
            try:
                page, text = self._locate(item.get("page"), _str(item.get("text")))
            except _Drop:
                continue
            hits.append({"page": page, "text": text})
        unique: list[dict] = []
        for h in hits:
            covered = any(
                h["page"] == u["page"] and n.norm(h["text"]) in n.norm(u["text"]) for u in unique
            )
            if not covered:
                unique = [u for u in unique if not (
                    u["page"] == h["page"] and n.norm(u["text"]) in n.norm(h["text"]))]
                unique.append(h)
        self.result.injection_suspected = sorted(unique, key=lambda h: h["page"])

    def finish(self) -> ExtractionResult:
        found = {f["name"] for f in self.result.fields}
        self.result.not_found = [name for name in expected_names(self.doc_type) if name not in found]
        return self.result


def extract_document(doc_id: str, doc_type: str, pages: list[str],
                     complete: Complete | None = None) -> ExtractionResult:
    """Structured, verified Fields from a document's per-page text.

    pages[0] is page 1; empty strings (scanned/unreadable pages) are ignored.
    complete(prompt, schema) -> dict is the model; defaults to app.llm.complete.
    """
    doc_type = normalize_type(doc_type)
    pages = [p if isinstance(p, str) else "" for p in pages]
    ex = _Extractor(doc_id, doc_type, pages)
    if not any(p.strip() for p in pages):
        ex.take_injections([])
        return ex.finish()

    complete = complete or _default_complete()
    raw = complete(build_prompt(doc_type, pages), build_schema(doc_type))
    raw = raw if isinstance(raw, dict) else {}
    for item in _items(raw.get("fields")):
        ex.take_field(item)
    for item in _items(raw.get("people")):
        ex.take_person(item)
    ex.take_injections(_items(raw.get("injection_suspected")))
    return ex.finish()
