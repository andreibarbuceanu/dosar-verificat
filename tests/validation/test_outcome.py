"""Outcome policy, docs/SPRINT2_CONTRACT.md section 7, driven by Role 4's rule catalog."""
from __future__ import annotations

import logging

import pytest

from app.models import Document, Field, Finding
from app.validation import (
    LITIGATION_SCORE_NOT_COMPUTED, EvidenceError, check_evidence, decide_outcome, split_findings,
)
from tests.validation.fakes import CATALOG, catalog_entry, tool

OK_TOOL = tool("anaf_financials", {"cui": "1", "year": 2024}, {"turnover": 1})


def finding(rule: str, result: str, evidence: list[str] | None = None,
            severity: str = "red") -> Finding:
    return Finding(id=f"finding-{rule}-C", rule_id=rule, severity=severity, result=result,
                   evidence=evidence if evidence is not None else [f"tool:{OK_TOOL.id}"],
                   explanation="x")


def clean(**results: str) -> list[Finding]:
    """R03/R13 pass, R04 unknown (optional), R12 deferred; override per rule."""
    base = {"R03": "pass", "R04": "unknown", "R12": "unknown", "R13": "pass"}
    base.update(results)
    return [finding(rule, result) for rule, result in sorted(base.items())]


def outcome(findings, tools=(OK_TOOL,), catalog=CATALOG, **kw):
    return decide_outcome("C", list(findings), list(tools), catalog, **kw)


# ---------- green ----------

def test_all_mandatory_pass_is_green_despite_deferred_and_optional_unknowns():
    result = outcome(clean())
    assert result.result == "green"
    assert [f.rule_id for f in result.findings] == ["R03", "R04", "R13"]   # R12 left out


def test_deferred_rule_is_never_a_pass_and_never_blocks_green():
    evaluated, not_checked = split_findings(clean(), CATALOG)
    assert [f.rule_id for f in not_checked] == ["R12"]
    assert "R12" not in [f.rule_id for f in evaluated]
    assert outcome(clean(R12="fail")).result == "green"      # even a bogus fail is ignored


# ---------- exceptions ----------

def test_any_evaluated_fail_is_exceptions_even_with_unknowns_and_unavailable_tools():
    down = tool("court_cases", {"cui": "1"}, None, status="unavailable")
    assert outcome(clean(R03="fail", R13="unknown"), tools=[OK_TOOL, down]).result == "exceptions"


def test_fail_on_optional_rule_is_exceptions():
    assert outcome(clean(R04="fail")).result == "exceptions"


def test_fail_on_rule_unknown_to_the_catalog_still_counts():
    assert outcome(clean() + [finding("R07", "fail")]).result == "exceptions"


# ---------- escalated ----------

@pytest.mark.parametrize("rule", ["R03", "R13"])   # mandatory red and mandatory amber
def test_unknown_on_any_mandatory_rule_is_escalated(rule):
    assert outcome(clean(**{rule: "unknown"})).result == "escalated"


def test_missing_mandatory_finding_is_unknown_and_logged(caplog):
    findings = [f for f in clean() if f.rule_id != "R13"]
    with caplog.at_level(logging.WARNING, logger="app.validation.outcome"):
        assert outcome(findings).result == "escalated"
    assert "mandatory rule R13 has no finding" in caplog.text


@pytest.mark.parametrize("status", ["unavailable", "not_found"])
def test_registry_not_ok_is_escalated_not_green(status):
    down = tool("onrc_company", {"cui": "1"}, None, status=status)
    assert outcome(clean(), tools=[OK_TOOL, down]).result == "escalated"


def test_empty_catalog_is_never_green():
    assert outcome(clean(), catalog=[]).result == "escalated"


def test_catalog_with_no_mandatory_rule_is_never_green():
    optional_only = [catalog_entry("R04", "red", implemented=True, mandatory=False)]
    assert outcome([finding("R04", "pass")], catalog=optional_only).result == "escalated"


def test_mandatory_but_not_implemented_rule_does_not_block():
    catalog = CATALOG + [catalog_entry("R15", "red", implemented=False, mandatory=True)]
    assert outcome(clean(), catalog=catalog).result == "green"


def test_missing_critical_evidence_is_escalated():
    assert outcome(clean(), missing_evidence=True).result == "escalated"


# ---------- no litigation score ----------

def test_litigation_score_is_the_documented_placeholder():
    result = outcome(clean())
    assert result.litigation_score == LITIGATION_SCORE_NOT_COMPUTED == 100
    assert result.deductions == []


# ---------- evidence ----------

def test_evidence_must_resolve_to_current_case():
    field = Field(id="d1-f1", name="turnover", value=1, doc_id="d1", page=1, quote="1")
    doc = Document(id="d1", type="bilant", file="b.pdf", pages=1)
    check_evidence([finding("R03", "fail", [f"field:{field.id}", f"tool:{OK_TOOL.id}"]),
                    finding("R14", "fail", [f"doc:{doc.id}"])],
                   [field], [OK_TOOL], [doc])
    with pytest.raises(EvidenceError):
        check_evidence([finding("R03", "fail", ["field:doc2-f3"])], [field], [OK_TOOL])
    with pytest.raises(EvidenceError):
        check_evidence([finding("R14", "fail", ["doc:other"])], [field], [OK_TOOL], [doc])


def test_fail_without_evidence_is_rejected():
    with pytest.raises(EvidenceError):
        check_evidence([finding("R03", "fail", [])], [], [OK_TOOL])


def test_duplicate_finding_ids_are_rejected():
    with pytest.raises(EvidenceError):
        check_evidence([finding("R03", "pass"), finding("R03", "pass")], [], [OK_TOOL])
