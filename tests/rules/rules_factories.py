"""Test doubles for the rules engine: valid app.models instances built from synthetic data.

Role 2 (tools) and Role 3 (comparisons) are not imported; their outputs are rebuilt here
from SPRINT2_CONTRACT.md sections 3 and 5.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import Document, Field, ToolResult
from app.rules import evaluate_rules

VALID_CUI = "41738200"      # control digit 0 is what 753217532 requires for 4173820
DEMO02_CUI = "41738203"     # the CUI in the DEMO-02 spec; its control digit is 3, not 0
FETCHED = datetime(2026, 10, 20, tzinfo=timezone.utc)


def fld(id: str, name: str, value: Any, doc_id: str = "bil-1", verified: bool = True) -> Field:
    return Field(id=id, name=name, value=value, doc_id=doc_id, page=1, quote=f"{name}: {value}", verified=verified)


def tool(id: str, name: str, data: dict | None, status: str = "ok", args: dict | None = None) -> ToolResult:
    return ToolResult(
        id=id, tool=name, args=args if args is not None else {"cui": VALID_CUI}, status=status,
        data=data, raw_ref=f"fixtures/registry/DEMO-02/{name}.json", fetched_at=FETCHED,
    )


def doc(id: str, type: str, readable: bool = True) -> Document:
    return Document(id=id, type=type, file=f"{id}.pdf", pages=1, readable=readable)


def cmp(check_id: str, rule_id: str | None, status: str, left: Any, left_ev: str | None,
        right: Any, right_ev: str | None, difference: Any = None) -> dict:
    """Role 3's ComparisonResult in its canonical JSON form (SPRINT2_CONTRACT §5.1)."""
    return {
        "check_id": check_id, "rule_id": rule_id, "status": status,
        "left": {"value": left, "evidence": left_ev}, "right": {"value": right, "evidence": right_ev},
        "difference": difference, "explanation": "test",
    }


def clean() -> dict[str, list]:
    """A file where every implemented rule passes."""
    fin = {"cui": VALID_CUI, "year": 2024, "currency": "RON", "turnover": 12400000, "net_profit": 520000,
           "source_mode": "simulated_fixture"}
    return {
        "fields": [
            fld("f-name", "company_name", "AGRO NORD TRANS SRL"),
            fld("f-cui", "cui", VALID_CUI),
            fld("f-cui-app", "cui", VALID_CUI, doc_id="app-1"),
            fld("f-appdate", "application_date", "2026-10-14", doc_id="app-1"),
            fld("f-fy", "fiscal_year", 2024),
            fld("f-turn", "turnover", 12400000),
            fld("f-np", "net_profit", 520000),
            fld("f-ta", "total_assets", 7300000),
            fld("f-eq", "equity", 2800000),
            fld("f-li", "liabilities", 4500000),
            fld("f-cafdate", "caf_issue_date", "2026-10-01", doc_id="caf-1"),
            fld("f-cafdebts", "caf_has_debts", False, doc_id="caf-1"),
            fld("f-dir", "director", {"name": "Andrei Mureșan"}, doc_id="app-1"),
            fld("f-ubo", "ubo", {"name": "Andrei Mureșan", "percent": 100}, doc_id="ubo-1"),
        ],
        "tools": [
            tool("t-fin", "anaf_financials", fin, args={"cui": VALID_CUI, "year": 2024}),
            tool("t-co", "anaf_company", {"cui": VALID_CUI, "active": True, "vat_registered": True,
                                          "vat_since": "2019-10-01", "vat_cancelled": None,
                                          "source_mode": "simulated_fixture"}),
            tool("t-onrc", "onrc_company", {"cui": VALID_CUI, "name": "AGRO NORD TRANS SRL",
                                            "source_mode": "simulated_fixture"}),
            tool("t-court", "court_cases", {"cui": VALID_CUI, "cases": [], "source_mode": "simulated_fixture"}),
        ],
        "comparisons": [
            cmp(f"cui:{VALID_CUI}", "R02", "match", VALID_CUI, "field:f-cui", VALID_CUI, "field:f-cui-app"),
            cmp(f"turnover:2024:{VALID_CUI}", "R03", "match", 12400000, "field:f-turn", 12400000, "tool:t-fin", 0),
            cmp(f"net_profit:2024:{VALID_CUI}", "R04", "match", 520000, "field:f-np", 520000, "tool:t-fin", 0),
            cmp("directors", "R10", "match", [{"name": "Andrei Mureșan"}], "field:f-dir",
                [{"name": "Andrei Mureșan"}], "tool:t-onrc"),
            cmp("ubo", "R11", "match", [{"name": "Andrei Mureșan"}], "field:f-ubo",
                [{"name": "Andrei Mureșan"}], "tool:t-onrc"),
        ],
        "documents": [doc("app-1", "application"), doc("bil-1", "bilant"), doc("caf-1", "caf"),
                      doc("onrc-1", "onrc"), doc("ubo-1", "ubo")],
    }


ENFORCEMENT_CASE = {
    "number": "2318/117/2025", "subject": "executare silită", "category": "enforcement",
    "party_role": "debitor", "status": "open", "registered": "2025-05-12",
    "court": "Tribunalul Cluj", "other_party": "LEASING FICTIV IFN SA",
}


def demo02() -> dict[str, list]:
    """DEMO-02: AGRO NORD TRANS SRL, CUI 41738203. PDF turnover 12.400.000, simulated ANAF 8.100.000,
    open enforcement case 2318/117/2025."""
    inputs = clean()
    for f in inputs["fields"]:
        if f.name == "cui":
            f.value = DEMO02_CUI
    for t in inputs["tools"]:
        t.args = {**t.args, "cui": DEMO02_CUI}
        t.data = {**t.data, "cui": DEMO02_CUI}
        if t.tool == "anaf_financials":
            t.data["turnover"], t.data["net_profit"] = 8100000, 520000
        if t.tool == "court_cases":
            t.data["cases"] = [dict(ENFORCEMENT_CASE)]
    inputs["comparisons"] = [
        c for c in inputs["comparisons"] if c["rule_id"] not in ("R02", "R03")
    ] + [cmp(f"turnover:2024:{DEMO02_CUI}", "R03", "mismatch", 12400000, "field:f-turn",
             8100000, "tool:t-fin", 4300000)]
    return inputs


def run(inputs: dict[str, list], case_id: str = "DEMO-02", **overrides) -> dict[str, Any]:
    """Findings keyed by rule id."""
    args = {"fields": inputs["fields"], "tool_results": inputs["tools"],
            "comparisons": inputs["comparisons"], "documents": inputs["documents"], **overrides}
    findings = evaluate_rules(case_id, **args)
    return {f.rule_id: f for f in findings}


def field_of(inputs: dict, id: str) -> Field:
    return next(f for f in inputs["fields"] if f.id == id)


def tool_of(inputs: dict, id: str) -> ToolResult:
    return next(t for t in inputs["tools"] if t.id == id)


def drop_fields(inputs: dict, *ids: str) -> dict:
    inputs["fields"] = [f for f in inputs["fields"] if f.id not in ids]
    return inputs
