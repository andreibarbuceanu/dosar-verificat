"""build_orchestrator / run_verification: one place for dependencies, never raises."""
from __future__ import annotations

import logging

import pytest

import app.validation.wiring as wiring
from app.models import Document, Field
from app.pipeline import run_pipeline
from app.validation import VerificationOrchestrator
from app.validation.doubles import NoComparisons, NoRules, UnavailableRegistryTools
from app.validation.wiring import build_orchestrator, run_verification, verification_report
from tests.validation.fakes import FakeRulesEngine

ALL_DOUBLES = ("registry_tools", "comparison_engine", "rules_engine")

DOCS = [Document(id="bil", type="bilant", file="b.pdf", pages=1)]
FIELDS = [Field(id="bil-f1", name="cui", value="41738203", doc_id="bil", page=1, quote="41738203"),
          Field(id="bil-f2", name="fiscal_year", value=2024, doc_id="bil", page=1, quote="2024")]


def test_build_orchestrator_warns_about_every_double(caplog, monkeypatch):
    monkeypatch.setattr(wiring, "_registry_tools", lambda: None)
    monkeypatch.setattr(wiring, "_comparison_engine", lambda: None)
    monkeypatch.setattr(wiring, "_rules_engine", lambda: None)      # app.rules not merged
    with caplog.at_level(logging.WARNING, logger="app.validation.wiring"):
        orch = build_orchestrator()
    assert "using test doubles for: registry_tools, comparison_engine, rules_engine" in caplog.text
    assert orch.doubles == ALL_DOUBLES
    assert isinstance(orch.rules, NoRules)


def test_build_orchestrator_uses_real_rules_once_importable(caplog, monkeypatch):
    real = FakeRulesEngine()                                          # stands in for app.rules
    monkeypatch.setattr(wiring, "_registry_tools", lambda: None)
    monkeypatch.setattr(wiring, "_comparison_engine", lambda: None)
    monkeypatch.setattr(wiring, "_rules_engine", lambda: real)
    with caplog.at_level(logging.WARNING, logger="app.validation.wiring"):
        orch = build_orchestrator()
    assert "using test doubles for: registry_tools, comparison_engine" in caplog.text
    assert "rules_engine" not in caplog.text
    assert orch.rules is real and orch.doubles == ("registry_tools", "comparison_engine")


def test_build_orchestrator_uses_all_merged_modules():
    orch = build_orchestrator()
    assert orch.doubles == ()
    assert orch.tools is wiring._registry_tools()
    assert isinstance(orch.comparisons, wiring._VerificationAdapter)


def test_doubles_invent_nothing_and_never_give_green():
    orch = VerificationOrchestrator(UnavailableRegistryTools(), NoComparisons(), NoRules(),
                                    doubles=ALL_DOUBLES)
    result = run_verification("C", DOCS, FIELDS, orch)
    assert {t.status for t in result.tool_results} == {"unavailable"}
    assert all(t.data is None and t.raw_ref is None for t in result.tool_results)
    assert result.comparisons == [] and result.findings == []
    assert result.outcome.result == "escalated"
    assert verification_report(result)["status"] == "not_available"


def test_crashing_orchestrator_is_recorded_and_escalated():
    class Crashing(VerificationOrchestrator):
        def run(self, case, fields):
            raise RuntimeError("boom")

    result = run_verification("C", DOCS, FIELDS, Crashing(None, None, None))
    assert result.status == "failed"
    assert result.errors == ["verification: boom"]
    assert result.outcome.result == "escalated" and result.outcome.findings == []
    report = verification_report(result)
    assert report["status"] == "failed" and report["result"] == "escalated"


def test_crashing_factory_is_recorded_and_escalated(monkeypatch):
    def broken():
        raise ImportError("app.rules missing")

    monkeypatch.setattr(wiring, "build_orchestrator", broken)
    result = run_verification("C", DOCS, FIELDS)
    assert result.status == "failed" and result.outcome.result == "escalated"
    assert "app.rules missing" in result.errors[0]


def test_pipeline_keeps_extraction_when_verification_crashes(monkeypatch):
    pytest.importorskip("pymupdf")
    from pathlib import Path

    monkeypatch.setenv("LLM_BACKEND", "replay")
    pdfs = sorted((Path(__file__).resolve().parents[2] / "pdfs" / "DEMO-02").glob("*.pdf"))

    def broken():
        raise RuntimeError("wiring bug")

    monkeypatch.setattr(wiring, "build_orchestrator", broken)
    result = run_pipeline("DEMO-02", [(p.stem, p) for p in pdfs])

    assert [d.document_type for d in result.documents] == ["unknown", "application", "bilant", "caf", "onrc"]
    assert next(f for f in result.fields if f.name == "turnover").value == 12_400_000
    assert result.validation["status"] == "failed"
    assert result.verification.outcome.result == "escalated"
