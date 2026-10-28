"""Fakes for Roles 2-4, shaped like docs/SPRINT2_CONTRACT.md sections 4-6.

They satisfy the RegistryTools / ComparisonEngine / RulesEngine protocols
until the real modules are merged. Registry data is written by each test,
never read from ground truth.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import Field, Finding, ToolResult
from app.validation import VerificationOrchestrator

FETCHED_AT = datetime(2026, 10, 20, tzinfo=timezone.utc)


def tool(name: str, args: dict, data: dict | None, status: str = "ok") -> ToolResult:
    suffix = "-".join(str(v) for v in args.values())
    return ToolResult(
        id=f"t-{name}-{suffix}", tool=name, args=args,
        status=status, data=data if status == "ok" else None,
        raw_ref=f"test-fake/{name}.json", fetched_at=FETCHED_AT,
    )


class FakeRegistryTools:
    """Role 2 fake. ``answers[tool]`` is a data dict, a status string, or an
    Exception to raise; a tool without an answer is ``not_found``."""

    def __init__(self, answers: dict[str, Any]):
        self.answers = answers
        self.calls: list[tuple] = []

    def _answer(self, name: str, args: dict) -> ToolResult:
        self.calls.append((name, *args.values()))
        answer = self.answers.get(name, "not_found")
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, str):
            return tool(name, args, None, status=answer)
        return tool(name, args, answer)

    def get_anaf_company(self, cui: str) -> ToolResult:
        return self._answer("anaf_company", {"cui": cui})

    def get_anaf_financials(self, cui: str, year: int) -> ToolResult:
        return self._answer("anaf_financials", {"cui": cui, "year": year})

    def get_onrc_company(self, cui: str) -> ToolResult:
        return self._answer("onrc_company", {"cui": cui})

    def get_court_cases(self, cui: str) -> ToolResult:
        return self._answer("court_cases", {"cui": cui})


class FakeComparisonEngine:
    """Role 3 fake producing the section 5.1 JSON shape for R03 turnover."""

    def compare(self, fields: list[Field], tool_results: list[ToolResult],
                *, fiscal_year: int) -> list[dict[str, Any]]:
        pdf = next((f for f in fields if f.name == "turnover" and f.verified), None)
        reg = next((t for t in tool_results if t.tool == "anaf_financials"), None)
        left = {"value": pdf.value if pdf else None, "evidence": f"field:{pdf.id}" if pdf else None}
        right = {"value": None, "evidence": f"tool:{reg.id}" if reg else None}
        status, difference = "unknown", None
        if pdf and reg and reg.status == "ok" and reg.data.get("year") == fiscal_year \
                and reg.data.get("currency") == "RON":
            right["value"] = reg.data["turnover"]
            difference = abs(pdf.value - right["value"])
            status = "match" if difference == 0 else "mismatch"
        return [{
            "check_id": f"turnover:{fiscal_year}", "rule_id": "R03", "status": status,
            "left": left, "right": right, "difference": difference,
            "explanation": "Cifra de afaceri: bilanț vs registru financiar simulat.",
        }]


def catalog_entry(rule_id: str, severity: str, implemented: bool, mandatory: bool) -> dict:
    """Same keys as Role 4's rule_catalog()."""
    return {"rule_id": rule_id, "description": f"{rule_id} (fake)", "severity": severity,
            "implemented": implemented, "mandatory": mandatory, "inputs": [], "thresholds": {}}


# A slice of Role 4's rules.yaml: mandatory R03/R13, optional R04, deferred R12.
CATALOG = [
    catalog_entry("R03", "red", implemented=True, mandatory=True),
    catalog_entry("R04", "red", implemented=True, mandatory=False),
    catalog_entry("R12", "red", implemented=False, mandatory=False),
    catalog_entry("R13", "amber", implemented=True, mandatory=True),
]


class FakeRulesEngine:
    """Role 4 fake: one Finding per catalog rule, sorted, id ``finding-{rule}-{case}``,
    section 6.1 mapping for R03, scenario alert for R13, R04 always unknown
    (no comparison yet), R12 deferred."""

    def __init__(self, catalog: list[dict] | None = None):
        self.catalog = CATALOG if catalog is None else catalog

    def rule_catalog(self) -> list[dict]:
        return [dict(r) for r in self.catalog]

    def evaluate_rules(self, case_id: str, fields, tool_results, comparisons: list[dict],
                       documents=None) -> list[Finding]:
        verdicts = {
            "R03": self._r03(comparisons),
            "R04": ("unknown", "amber", [], "Comparația R04 nu este disponibilă."),
            "R12": ("unknown", "red", [], "Neimplementat în Sprint 2: sursă de sancțiuni neintegrată."),
            "R13": self._r13(tool_results),
        }
        return [
            Finding(id=f"finding-{rule}-{case_id}", rule_id=rule, severity=severity,
                    result=result, evidence=evidence, explanation=explanation)
            for rule, (result, severity, evidence, explanation) in sorted(verdicts.items())
            if rule in {r["rule_id"] for r in self.catalog}
        ]

    @staticmethod
    def _r03(comparisons: list[dict]):
        c = next((c for c in comparisons if c["rule_id"] == "R03"), None)
        if c is None:
            return "unknown", "amber", [], "Comparația R03 lipsește."
        refs = [s["evidence"] for s in (c["left"], c["right"]) if s["evidence"]]
        result, severity = {"mismatch": ("fail", "red"), "match": ("pass", "red"),
                            "unknown": ("unknown", "amber")}[c["status"]]
        return result, severity, refs if result != "unknown" else [], c["explanation"]

    @staticmethod
    def _r13(tool_results: list[ToolResult]):
        court = next((t for t in tool_results if t.tool == "court_cases"), None)
        if court is None or court.status != "ok":
            return "unknown", "amber", [], "Registrul instanțelor nu a răspuns."
        if any(x.get("status") == "open" for x in court.data.get("cases", [])):
            return "fail", "amber", [f"tool:{court.id}"], "Executare silită deschisă (registru simulat)."
        return "pass", "amber", [f"tool:{court.id}"], "Niciun dosar deschis (registru simulat)."


def orchestrator(tools: FakeRegistryTools) -> VerificationOrchestrator:
    return VerificationOrchestrator(tools, FakeComparisonEngine(), FakeRulesEngine())


def financials(cui: str, turnover: int, year: int = 2024) -> dict:
    return {"cui": cui, "year": year, "currency": "RON", "turnover": turnover}


def court(cui: str, *open_numbers: str) -> dict:
    return {"cui": cui, "cases": [
        {"number": n, "subject": "executare silită", "category": "enforcement",
         "party_role": "debitor", "status": "open", "registered": "2025-05-12"}
        for n in open_numbers
    ]}
