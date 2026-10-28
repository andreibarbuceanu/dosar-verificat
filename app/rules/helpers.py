"""Evaluation context and small pure helpers shared by the rules. No I/O, no clock."""
from __future__ import annotations

import dataclasses
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

# ---------------------------------------------------------------- inputs as dicts


def to_dict(obj: Any) -> dict[str, Any]:
    """Pydantic models, dataclasses and plain dicts all become dicts; the input is not changed."""
    if isinstance(obj, dict):
        return obj
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return dump()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    attrs = getattr(obj, "__dict__", None)
    if attrs is not None:
        return dict(attrs)
    raise TypeError(f"cannot read {type(obj).__name__} as a record")


# ---------------------------------------------------------------- values


def fold(text: Any) -> str:
    """Lowercase, no diacritics, single spaces. For comparing names and keywords."""
    decomposed = unicodedata.normalize("NFD", str(text or ""))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plain.casefold()).strip()


def to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str) and re.fullmatch(r"-?\d+(\.\d+)?", value.strip()):
        return Decimal(value.strip())
    return None


def to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        for pattern, order in ((r"(\d{4})-(\d{2})-(\d{2})", (0, 1, 2)), (r"(\d{2})\.(\d{2})\.(\d{4})", (2, 1, 0))):
            m = re.fullmatch(pattern, text[:10])
            if m:
                parts = [int(m.group(i + 1)) for i in order]
                try:
                    return date(*parts)
                except ValueError:
                    return None
    return None


def add_months(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    last = [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(day.day, last))


def parse_cui(value: Any) -> str | None:
    """Digits of a CUI, without the RO prefix; None when it is not numeric."""
    text = re.sub(r"[\s.\-]", "", str(value or "")).upper()
    if text.startswith("RO"):
        text = text[2:]
    return text if text.isdigit() else None


_CUI_WEIGHTS = (7, 5, 3, 2, 1, 7, 5, 3, 2)


def cui_control_digit(cui: str) -> int:
    """Control digit the first digits of this CUI require (weights 753217532)."""
    total = sum(int(d) * w for d, w in zip(cui[:-1].zfill(9), _CUI_WEIGHTS))
    remainder = total * 10 % 11
    return 0 if remainder == 10 else remainder


# ---------------------------------------------------------------- formatting (Romanian)


def fmt_num(value: Decimal | int | float) -> str:
    d = to_decimal(value)
    if d is None:
        return str(value)
    if d == d.to_integral_value():
        return f"{int(d):,}".replace(",", ".")
    text = f"{d:,.2f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def fmt_money(value: Any, currency: str = "RON") -> str:
    return f"{fmt_num(value)} {currency}"


def fmt_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def fmt_value(value: Any, currency: str | None = None) -> str:
    """A compared value as an analyst reads it."""
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return fmt_money(value, currency) if currency else fmt_num(value)
    if isinstance(value, list):
        names = [str(v.get("name")) if isinstance(v, dict) and v.get("name") else str(v) for v in value]
        return ", ".join(names) if names else "(listă goală)"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)[:120]
    return "(lipsă)" if value is None else str(value)


# ---------------------------------------------------------------- labels

_DOC_LABELS = {
    "bilant": "bilanț",
    "application": "cererea de credit",
    "caf": "certificatul de atestare fiscală",
    "onrc": "certificatul ONRC",
    "ubo": "declarația beneficiarului real",
    "unknown": "documentul",
}
_TOOL_LABELS = {
    "anaf_company": "registrul ANAF",
    "anaf_financials": "registrul ANAF",
    "onrc_company": "registrul ONRC",
    "court_cases": "portalul instanțelor",
}


def is_simulated(tool: dict[str, Any]) -> bool:
    data = tool.get("data") if isinstance(tool.get("data"), dict) else {}
    mode = fold(data.get("source_mode"))
    raw_ref = fold(tool.get("raw_ref"))
    return "simul" in mode or "fixture" in mode or "fixture" in raw_ref or "mock" in raw_ref


def tool_label(tool: dict[str, Any]) -> str:
    base = _TOOL_LABELS.get(tool.get("tool"), f"registrul {tool.get('tool')}")
    return f"{base} (simulat)" if is_simulated(tool) else base


def problem_message(tools: list[dict[str, Any]]) -> str:
    """Why registry results cannot be used (status not ok)."""
    if any(t.get("status") == "unavailable" for t in tools):
        return "registru indisponibil, verificare manuală"
    return "nu există date în registru"


# ---------------------------------------------------------------- context


@dataclass(frozen=True)
class Verdict:
    result: str                       # pass | fail | unknown
    explanation: str
    evidence: tuple[str, ...] = ()
    severity: str | None = None       # None = the rule's own severity


@dataclass
class Context:
    case_id: str
    fields: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    comparisons: list[dict[str, Any]]
    documents: list[dict[str, Any]] | None
    rule_cfg: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.field_by_id = {f["id"]: f for f in self.fields if "id" in f}
        self.tool_by_id = {t["id"]: t for t in self.tools if "id" in t}
        self.doc_by_id = {d["id"]: d for d in (self.documents or []) if "id" in d}

    # thresholds of the rule being evaluated
    def th(self, name: str) -> Any:
        return self.rule_cfg["thresholds"][name]["value"]

    # fields: only verified ones are evidence
    def verified(self, name: str) -> list[dict[str, Any]]:
        return [f for f in self.fields if f.get("name") == name and f.get("verified") is True]

    def single_value(self, name: str) -> tuple[dict[str, Any] | None, str | None]:
        """The one verified field with this name, or why there is none (missing / conflicting)."""
        found = self.verified(name)
        if not found:
            return None, f"câmpul „{name}” lipsește sau nu este verificat"
        keys = {self.value_key(f.get("value")) for f in found}
        if len(keys) > 1:
            return None, f"câmpul „{name}” are valori contradictorii în dosar"
        return found[0], None

    @staticmethod
    def value_key(value: Any) -> str:
        number = to_decimal(value)
        return f"n:{number.normalize()}" if number is not None else "j:" + json.dumps(value, sort_keys=True, default=str)

    def tools_named(self, name: str) -> list[dict[str, Any]]:
        return [t for t in self.tools if t.get("tool") == name]

    def case_cuis(self) -> set[str]:
        return {c for f in self.verified("cui") if (c := parse_cui(f.get("value")))}

    def case_names(self) -> list[str]:
        return [str(f["value"]) for f in self.verified("company_name") if f.get("value")]

    def resolve(self, ref: Any) -> tuple[str, dict[str, Any]] | None:
        """("field"|"tool", record) for a reference that exists in the inputs; else None."""
        if not isinstance(ref, str) or ":" not in ref:
            return None
        kind, _, ident = ref.partition(":")
        table = {"field": self.field_by_id, "tool": self.tool_by_id, "doc": self.doc_by_id}.get(kind)
        record = table.get(ident) if table is not None else None
        return (kind, record) if record is not None else None

    def doc_label(self, doc_id: str) -> str:
        doc = self.doc_by_id.get(doc_id)
        label = _DOC_LABELS.get(doc.get("type")) if doc else None
        return f"{label} ({doc_id})" if label else f"documentul {doc_id}"

    def field_source(self, record: dict[str, Any]) -> str:
        return self.doc_label(record.get("doc_id", "?"))

    def usable_registry(self, tool_name: str) -> tuple[list[dict[str, Any]], str | None]:
        """ok results of this tool for the case's company, or the reason there are none."""
        tools = self.tools_named(tool_name)
        if not tools:
            return [], f"{_TOOL_LABELS.get(tool_name, tool_name)} nu a fost interogat"
        ok = [t for t in tools if t.get("status") == "ok" and isinstance(t.get("data"), dict)]
        if not ok:
            return [], problem_message(tools)
        cuis = self.case_cuis()
        if not cuis:
            return ok, None
        matching = []
        for tool in ok:
            queried = parse_cui((tool.get("args") or {}).get("cui") or tool["data"].get("cui"))
            if queried in cuis:
                matching.append(tool)
        if not matching:
            return [], "CUI-ul interogat în registru diferă de cel din documente"
        return matching, None


def unique(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))
