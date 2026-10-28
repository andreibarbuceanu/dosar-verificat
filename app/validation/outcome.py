"""Outcome policy from ``docs/SPRINT2_CONTRACT.md`` section 7.

Pure function of findings, tool results and Role 4's ``rule_catalog()``: no
registry calls, no rule evaluation, no ground truth. Which rules are
implemented or mandatory comes only from the catalog, never from this file.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

from app.models import Document, Field, Finding, Outcome, ToolResult

log = logging.getLogger(__name__)

# Contract 7.1: Outcome requires litigation_score, but no scoring policy is
# approved. 100 here means "not computed", never "no litigation risk".
LITIGATION_SCORE_NOT_COMPUTED = 100

Catalog = list[dict[str, Any]]


class EvidenceError(ValueError):
    """A finding breaks the evidence rules (contract principle 4)."""


def check_evidence(findings: Iterable[Finding], fields: Iterable[Field],
                   tool_results: Iterable[ToolResult], documents: Iterable[Document] = ()) -> None:
    """Every ref must name a real Field, ToolResult or (R14) Document; a fail needs one."""
    known = ({f"field:{f.id}" for f in fields} | {f"tool:{t.id}" for t in tool_results}
             | {f"doc:{d.id}" for d in documents})
    seen: set[str] = set()
    for finding in findings:
        if finding.id in seen:
            raise EvidenceError(f"Duplicate finding id {finding.id}")
        seen.add(finding.id)
        missing = [ref for ref in finding.evidence if ref not in known]
        if missing:
            raise EvidenceError(f"Finding {finding.id} cites unknown evidence: {missing}")
        if finding.result == "fail" and not finding.evidence:
            raise EvidenceError(f"Finding {finding.id} fails without evidence")


def split_findings(findings: list[Finding], catalog: Catalog) -> tuple[list[Finding], list[Finding]]:
    """(evaluated, not_checked). A rule the catalog does not know counts as
    evaluated, so its fail can never be hidden."""
    implemented = {r["rule_id"]: r["implemented"] for r in catalog}
    evaluated = [f for f in findings if implemented.get(f.rule_id, True)]
    not_checked = [f for f in findings if not implemented.get(f.rule_id, True)]
    return evaluated, not_checked


def mandatory_rules(catalog: Catalog) -> list[str]:
    return [r["rule_id"] for r in catalog if r["implemented"] and r["mandatory"]]


def missing_mandatory(findings: list[Finding], catalog: Catalog) -> list[str]:
    present = {f.rule_id for f in findings}
    return [rule for rule in mandatory_rules(catalog) if rule not in present]


def decide_outcome(
    case_id: str,
    findings: list[Finding],
    tool_results: list[ToolResult],
    catalog: Catalog,
    *,
    missing_evidence: bool = False,
) -> Outcome:
    """Contract 7, with implemented/mandatory taken from the rule catalog:

    1. any evaluated fail                                   -> exceptions
    2. a mandatory rule unknown or missing, a registry not
       ``ok``, missing critical input, or no mandatory rule  -> escalated
    3. every mandatory rule passed                           -> green

    Not-implemented rules never block green and never count as pass; they are
    left out of ``Outcome.findings`` (contract 7: evaluated findings).
    ``missing_evidence`` is set by the caller when critical input (e.g. the
    CUI) was missing or a stage failed.
    """
    evaluated, _ = split_findings(findings, catalog)
    results: dict[str, set[str]] = {}
    for f in evaluated:
        results.setdefault(f.rule_id, set()).add(f.result)

    mandatory = mandatory_rules(catalog)
    for rule in missing_mandatory(evaluated, catalog):
        log.warning("case %s: mandatory rule %s has no finding; treated as unknown", case_id, rule)

    if any("fail" in r for r in results.values()):
        result = "exceptions"
    elif (
        missing_evidence
        or not mandatory                                   # 7.4: zero checks is never green
        or any(t.status != "ok" for t in tool_results)
        or any(results.get(rule) != {"pass"} for rule in mandatory)
    ):
        result = "escalated"
    else:
        result = "green"

    return Outcome(
        case_id=case_id,
        result=result,
        litigation_score=LITIGATION_SCORE_NOT_COMPUTED,
        deductions=[],
        findings=evaluated,
    )
