"""VerificationOrchestrator with Role 2-4 fakes: inputs only from verified fields."""
from __future__ import annotations

import logging

from app.models import Case, Document, Field, Finding
from app.validation import VerificationOrchestrator, normalize_cui
from tests.validation.fakes import (
    CATALOG, FakeComparisonEngine, FakeRegistryTools, FakeRulesEngine, court, financials, orchestrator,
)

CUI = "41738203"
CASE = Case(id="C-1", company_name="X SRL", cui=CUI, status="running", documents=[
    Document(id="app", type="application", file="a.pdf", pages=1),
    Document(id="bil", type="bilant", file="b.pdf", pages=2),
])


def fld(fid: str, name: str, value, doc_id: str = "bil", verified: bool = True) -> Field:
    return Field(id=fid, name=name, value=value, doc_id=doc_id, page=1,
                 quote=str(value), verified=verified)


def demo_fields(turnover: int = 12_400_000) -> list[Field]:
    return [fld("app-f1", "cui", CUI, "app"), fld("bil-f1", "cui", CUI),
            fld("bil-f2", "fiscal_year", 2024), fld("bil-f3", "turnover", turnover)]


def registry(turnover: int = 8_100_000, **overrides) -> FakeRegistryTools:
    answers = {"anaf_company": {"cui": CUI, "active": True},
               "anaf_financials": financials(CUI, turnover),
               "onrc_company": {"cui": CUI, "name": "X SRL"},
               "court_cases": court(CUI)}
    answers.update(overrides)
    return FakeRegistryTools(answers)


# ---------- happy path ----------

def test_happy_path_turnover_mismatch_is_r03_fail_and_exceptions():
    tools = registry()
    result = orchestrator(tools).run(CASE, demo_fields())

    assert [c[0] for c in tools.calls] == ["anaf_company", "anaf_financials", "onrc_company", "court_cases"]
    assert ("anaf_financials", CUI, 2024) in tools.calls
    assert result.status == "completed" and result.errors == []
    assert result.stages == {"inputs": "ok", "registries": "ok", "comparisons": "ok",
                             "rules": "ok", "outcome": "ok"}
    [comparison] = result.comparisons
    assert comparison["status"] == "mismatch" and comparison["difference"] == 4_300_000
    r03 = by_rule(result)["R03"]
    assert (r03.id, r03.result, r03.severity) == ("finding-R03-C-1", "fail", "red")
    assert r03.evidence == ["field:bil-f3", "tool:t-anaf_financials-41738203-2024"]
    assert result.outcome.result == "exceptions"
    assert result.outcome.findings == result.findings
    assert [f.rule_id for f in result.not_checked] == ["R12"]
    assert result.catalog == CATALOG
    assert result.outcome.litigation_score == 100 and result.outcome.deductions == []


def by_rule(result) -> dict:
    return {f.rule_id: f for f in result.findings}


def test_clean_match_is_green_with_r12_not_checked_and_r04_unknown():
    result = orchestrator(registry()).run(CASE, demo_fields(turnover=8_100_000))
    assert {r: f.result for r, f in by_rule(result).items()} == {
        "R03": "pass", "R04": "unknown", "R13": "pass"}
    assert [f.rule_id for f in result.not_checked] == ["R12"]
    assert result.outcome.result == "green"


def test_mandatory_rule_missing_from_engine_output_escalates():
    class DropsR13(FakeRulesEngine):
        def evaluate_rules(self, *a, **k):
            return [f for f in super().evaluate_rules(*a, **k) if f.rule_id != "R13"]

    result = VerificationOrchestrator(registry(), FakeComparisonEngine(), DropsR13()).run(
        CASE, demo_fields(turnover=8_100_000))
    assert result.stages["rules"] == "error"
    assert result.errors == ["R13: regula obligatorie nu are rezultat; tratată ca necunoscută."]
    assert result.outcome.result == "escalated"


def test_doc_evidence_from_r14_is_accepted():
    class WithR14(FakeRulesEngine):
        def evaluate_rules(self, case_id, *a, **k):
            return super().evaluate_rules(case_id, *a, **k) + [Finding(
                id=f"finding-R14-{case_id}", rule_id="R14", severity="amber", result="pass",
                evidence=["doc:app", "doc:bil"], explanation="Documente prezente.")]

    result = VerificationOrchestrator(registry(), FakeComparisonEngine(), WithR14()).run(
        CASE, demo_fields(turnover=8_100_000))
    assert result.stages["rules"] == "ok" and by_rule(result)["R14"].result == "pass"


def test_open_court_case_is_r13_scenario_exception():
    tools = registry(turnover=12_400_000, court_cases=court(CUI, "2318/117/2025"))
    result = orchestrator(tools).run(CASE, demo_fields())
    assert {r: f.result for r, f in by_rule(result).items()} == {
        "R03": "pass", "R04": "unknown", "R13": "fail"}
    assert result.outcome.result == "exceptions"


def test_each_stage_is_logged_with_case_and_duration(caplog):
    with caplog.at_level(logging.INFO, logger="app.validation.orchestrator"):
        orchestrator(registry()).run(CASE, demo_fields())
    timed = [r for r in caplog.records if hasattr(r, "duration_ms")]
    assert [r.stage for r in timed] == ["inputs", "registries", "comparisons", "rules", "outcome"]
    assert all(r.case_id == "C-1" and r.duration_ms >= 0 for r in timed)


# ---------- one tool raising ----------

def test_raising_tool_becomes_unavailable_and_run_escalates():
    tools = registry(turnover=8_100_000, court_cases=TimeoutError("portal.just.ro timeout"))
    result = orchestrator(tools).run(CASE, demo_fields(turnover=8_100_000))

    court_result = next(t for t in result.tool_results if t.tool == "court_cases")
    assert court_result.status == "unavailable" and court_result.data is None
    assert court_result.args == {"cui": CUI}
    assert len(result.tool_results) == 4                  # the other tools still ran
    assert result.errors == ["court_cases: portal.just.ro timeout"]
    assert result.stages["registries"] == "error" and result.stages["rules"] == "ok"
    assert result.status == "completed_with_errors"
    assert by_rule(result)["R13"].result == "unknown"
    assert result.outcome.result == "escalated"           # R03 passed, but not green


def test_raising_financials_tool_makes_r03_unknown():
    tools = registry(anaf_financials=ConnectionError("ANAF down"))
    result = orchestrator(tools).run(CASE, demo_fields())
    assert by_rule(result)["R03"].result == "unknown"
    assert result.outcome.result == "escalated"


def test_raising_comparison_or_rules_engine_never_crashes():
    class Boom:
        def compare(self, *a, **k):
            raise RuntimeError("compare bug")

        def rule_catalog(self):
            return CATALOG

        def evaluate_rules(self, *a, **k):
            raise RuntimeError("rules bug")

    result = VerificationOrchestrator(registry(), Boom(), Boom()).run(CASE, demo_fields())
    assert result.stages["comparisons"] == "error" and result.stages["rules"] == "error"
    assert result.errors == ["comparisons: compare bug", "rules: rules bug"]
    assert result.outcome.result == "escalated" and result.findings == []


def test_rules_citing_unknown_evidence_are_dropped_and_escalated():
    class BadRules(FakeRulesEngine):
        def evaluate_rules(self, *a, **k):
            return [Finding(id="f", rule_id="R03", severity="red", result="fail",
                            evidence=["field:doc2-f3"], explanation="x")]

    result = VerificationOrchestrator(registry(), FakeComparisonEngine(), BadRules()).run(
        CASE, demo_fields())
    assert result.findings == [] and result.stages["rules"] == "error"
    assert result.outcome.result == "escalated"


# ---------- missing CUI ----------

def test_missing_cui_skips_tools_and_escalates():
    tools = registry()
    fields = [fld("bil-f1", "cui", CUI, verified=False), fld("bil-f2", "fiscal_year", 2024),
              fld("bil-f3", "turnover", 1)]
    result = orchestrator(tools).run(CASE, fields)

    assert tools.calls == []
    assert result.tool_results == [] and result.findings == []
    assert result.stages == {"inputs": "error", "registries": "skipped", "comparisons": "skipped",
                             "rules": "skipped", "outcome": "ok"}
    assert "CUI" in result.errors[0]
    assert result.outcome.result == "escalated"


def test_conflicting_cuis_skip_tools_and_escalate():
    tools = registry()
    result = orchestrator(tools).run(CASE, demo_fields() + [fld("app-f2", "cui", "11111111", "app")])
    assert tools.calls == []
    assert "11111111" in result.errors[0]
    assert result.outcome.result == "escalated"


def test_ro_prefix_and_spaces_are_the_same_cui():
    assert normalize_cui(" ro 4173 8203") == normalize_cui("RO41738203") == CUI
    tools = registry()
    fields = demo_fields()
    fields[0] = fld("app-f1", "cui", "RO 41738203", "app")
    assert orchestrator(tools).run(CASE, fields).errors == []


def test_missing_fiscal_year_skips_financials_and_comparisons():
    tools = registry()
    fields = [f for f in demo_fields() if f.name != "fiscal_year"] + [fld("app-f9", "fiscal_year", 2024, "app")]
    result = orchestrator(tools).run(CASE, fields)
    assert "anaf_financials" not in [c[0] for c in tools.calls]   # year only counts from the bilant
    assert result.stages["comparisons"] == "skipped" and result.comparisons == []
    assert result.outcome.result == "escalated"


# ---------- rerun idempotent ----------

def test_rerun_replaces_previous_results_instead_of_appending():
    orch = orchestrator(registry())
    first = orch.run(CASE, demo_fields())
    case = first.apply_to(CASE)
    second = orch.run(case, demo_fields())
    case = second.apply_to(case)

    assert [t.id for t in case.tool_results] == [t.id for t in first.tool_results]
    assert len(case.tool_results) == 4
    assert [f.id for f in case.outcome.findings] == [f.id for f in first.findings] == [
        "finding-R03-C-1", "finding-R04-C-1", "finding-R13-C-1"]
    assert case.status == "exceptions"
    assert case.documents == CASE.documents and case.id == CASE.id


def test_rerun_after_a_fix_drops_stale_results():
    failing = orchestrator(registry(court_cases=RuntimeError("down"))).run(CASE, demo_fields())
    case = failing.apply_to(CASE)
    assert any(t.status == "unavailable" for t in case.tool_results)

    fixed = orchestrator(registry(turnover=12_400_000)).run(case, demo_fields())
    case = fixed.apply_to(case)
    assert all(t.status == "ok" for t in case.tool_results)
    assert case.status == "green"
