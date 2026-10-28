"""DEMO-02 end to end: real PDFs -> real Sprint 1 pipeline -> Sprint 2 stage.

Company: AGRO NORD TRANS SRL. The PDFs carry CUI 41738200; the 41738203 used in
SPRINT2_CONTRACT §3 fails the CUI check digit (Role 4 R01), so this test pins
what the PDFs actually say. The registry fake answers for whatever CUI it is
asked, with 2024 turnover 8,100,000 RON and one open synthetic enforcement case.

Lives in tests/validation/ because SPRINT2_CONTRACT §1 gives tests/integration/
to Role 6; it can move there when they take it over.

What is real and what is still a stand-in, per assertion (tags in the tests):

  [REAL]        runs real code today: PDF processing, classification, extraction
                (LLM replay), field ids, orchestrator, outcome policy, API-free
                pipeline wiring, file-access check.
  [ROLE 4]      produced by the rules fake today. The same assertion also runs
                against the real app.rules in the ``rules-real`` variant, which is
                skipped until Role 4 merges and then runs automatically.
  [ROLE 2/3]    registry answers and the R03 comparison (and its difference)
                come from fakes until app.tools / app.verification are wired in
                app/validation/wiring.py; no variant covers them yet.
"""
from __future__ import annotations

import builtins
import io
import os
import pathlib
from pathlib import Path

import pytest

pytest.importorskip("pymupdf")

from app.pipeline import run_pipeline  # noqa: E402
from app.validation import LITIGATION_SCORE_NOT_COMPUTED, VerificationOrchestrator  # noqa: E402
from tests.validation.fakes import (  # noqa: E402
    FakeComparisonEngine, FakeRegistryTools, FakeRulesEngine, court, financials,
)

ROOT = Path(__file__).resolve().parents[2]
PDFS = sorted((ROOT / "pdfs" / "DEMO-02").glob("*.pdf"))
PDF_CUI = "41738200"
FORBIDDEN = ("expected", "planted_errors", "ground_truth", "companies.json")


def registry() -> FakeRegistryTools:
    """[ROLE 2/3] simulated registry answers, written here, never read from ground truth."""
    return FakeRegistryTools({
        "anaf_company": {"cui": PDF_CUI, "active": True, "vat_registered": True},
        "anaf_financials": financials(PDF_CUI, 8_100_000, year=2024),
        "onrc_company": {"cui": PDF_CUI, "name": "AGRO NORD TRANS SRL"},
        "court_cases": court(PDF_CUI, "2318/117/2025"),           # open enforcement, debtor
    })


def rules_engine(kind: str):
    if kind == "real":
        return pytest.importorskip("app.rules", reason="Role 4 app.rules not merged yet")
    return FakeRulesEngine()


class OpenSpy:
    """Records every path opened via builtins.open, io.open, Path.open and os.open."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch):
        self.paths: list[str] = []
        real_io, real_path, real_os = io.open, pathlib.Path.open, os.open

        def spy_open(file, *a, **k):
            self.paths.append(str(file))
            return real_io(file, *a, **k)

        def spy_path_open(path_self, *a, **k):
            self.paths.append(str(path_self))
            return real_path(path_self, *a, **k)

        def spy_os_open(path, *a, **k):
            self.paths.append(str(path))
            return real_os(path, *a, **k)

        monkeypatch.setattr(builtins, "open", spy_open)
        monkeypatch.setattr(io, "open", spy_open)
        monkeypatch.setattr(pathlib.Path, "open", spy_path_open)
        monkeypatch.setattr(os, "open", spy_os_open)


@pytest.fixture(params=["fake", "real"], ids=["rules-fake", "rules-real"])
def demo02(request, monkeypatch):
    """One pipeline run per rules engine, with every file open recorded."""
    monkeypatch.setenv("LLM_BACKEND", "replay")
    rules = rules_engine(request.param)
    tools = registry()
    orch = VerificationOrchestrator(tools, FakeComparisonEngine(), rules)
    spy = OpenSpy(monkeypatch)
    result = run_pipeline("DEMO-02", [(p.stem, p) for p in PDFS], orchestrator=orch)
    monkeypatch.undo()
    return result, tools, spy.paths


def refs(result) -> tuple[dict, dict]:
    v = result.verification
    return ({f"field:{f.id}": f for f in result.fields},
            {f"tool:{t.id}": t for t in v.tool_results})


def test_turnover_comes_from_the_pdf_with_page_and_quote(demo02):
    """[REAL] Sprint 1 extraction on the real bilanț PDF."""
    result, _, _ = demo02
    bilant_ids = {d.document_id for d in result.documents if d.document_type == "bilant"}
    [turnover] = [f for f in result.fields if f.name == "turnover"]

    assert turnover.value == 12_400_000
    assert turnover.doc_id in bilant_ids
    assert turnover.page >= 1 and "12.400.000" in turnover.quote
    assert turnover.verified is True


def test_registries_are_queried_with_the_cui_from_the_pdfs(demo02):
    """[REAL] the orchestrator reads CUI and fiscal year from verified fields only."""
    result, tools, _ = demo02
    assert {f.value for f in result.fields if f.name == "cui"} == {PDF_CUI}
    assert ("anaf_financials", PDF_CUI, 2024) in tools.calls


def test_r03_fails_with_difference_and_both_evidence_refs(demo02):
    result, _, _ = demo02
    v = result.verification
    fields, tools = refs(result)

    # [ROLE 2/3] the comparison and its difference come from the fakes for now.
    [r03_cmp] = [c for c in v.comparisons if c["rule_id"] == "R03"]
    assert r03_cmp["status"] == "mismatch"
    assert (r03_cmp["left"]["value"], r03_cmp["right"]["value"]) == (12_400_000, 8_100_000)
    assert r03_cmp["difference"] == 4_300_000

    # [ROLE 4] the finding; checked against real app.rules in the rules-real variant.
    [r03] = [f for f in v.findings if f.rule_id == "R03"]
    assert (r03.result, r03.severity) == ("fail", "red")
    cited_fields = [fields[r] for r in r03.evidence if r in fields]
    cited_tools = [tools[r] for r in r03.evidence if r in tools]
    assert [f.name for f in cited_fields if f.name == "turnover"] == ["turnover"]
    assert next(f for f in cited_fields if f.name == "turnover").value == 12_400_000
    assert [t.tool for t in cited_tools] == ["anaf_financials"]
    assert cited_tools[0].data["turnover"] == 8_100_000
    assert set(r03.evidence) <= set(fields) | set(tools)          # nothing dangling


def test_outcome_is_exceptions(demo02):
    """[REAL] outcome policy; [ROLE 4] the findings it is computed from."""
    result, _, _ = demo02
    assert result.verification.outcome.result == "exceptions"
    assert result.validation["result"] == "exceptions"


def test_r13_is_not_scored(demo02):
    """[REAL] no litigation score; [ROLE 4] R13 shape.

    The open enforcement case may surface as the R13 scenario alert (contract
    §6.1: amber, evidence = the court_cases tool result) or as unknown, but it
    never becomes a score or a deduction.
    """
    result, _, _ = demo02
    v = result.verification
    _, tools = refs(result)

    assert v.outcome.deductions == []
    assert v.outcome.litigation_score == LITIGATION_SCORE_NOT_COMPUTED   # placeholder, not a score
    for r13 in [f for f in v.findings if f.rule_id == "R13"]:
        assert r13.result in ("fail", "unknown")
        if r13.result == "fail":
            assert r13.severity == "amber"                 # enforcement alert, not red
        assert all(tools[r].tool == "court_cases" for r in r13.evidence)


def test_runtime_never_opens_ground_truth(demo02):
    """[REAL] for every module that ran (incl. app.rules in rules-real)."""
    _, _, opened = demo02
    assert any(p.endswith(".pdf") for p in opened), "spy saw no PDF opens; check would be vacuous"
    assert any("fixtures/llm" in p for p in opened)
    leaked = [p for p in opened if any(word in p for word in FORBIDDEN)]
    assert leaked == []


def test_open_spy_catches_a_ground_truth_read(monkeypatch):
    """[REAL] guards the check above: a module peeking at expected/ is detected."""
    monkeypatch.setenv("LLM_BACKEND", "replay")

    class PeekingRules(FakeRulesEngine):
        def evaluate_rules(self, *a, **k):
            (ROOT / "expected" / "intake_truth.json").read_text(encoding="utf-8")
            return super().evaluate_rules(*a, **k)

    orch = VerificationOrchestrator(registry(), FakeComparisonEngine(), PeekingRules())
    spy = OpenSpy(monkeypatch)
    run_pipeline("DEMO-02", [(p.stem, p) for p in PDFS], orchestrator=orch)
    monkeypatch.undo()
    assert any("expected" in p for p in spy.paths)
