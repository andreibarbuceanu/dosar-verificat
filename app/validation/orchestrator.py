"""Sprint 2 orchestration (Role 5): registries -> comparisons -> rules -> outcome.

The teammate modules are injected through the three Protocols below, so this
runs with fakes until app.tools, app.verification and app.rules are merged
(contract principle 9). Inputs are verified PDF fields and simulated registry
answers only; nothing here opens ground-truth files.
"""
from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Literal, Protocol

from app.models import Case, Document, Field, Finding, Outcome, ToolResult
from app.validation.outcome import (
    Catalog, EvidenceError, check_evidence, decide_outcome, missing_mandatory, split_findings,
)

log = logging.getLogger(__name__)

StageStatus = Literal["ok", "error", "skipped"]


class RegistryTools(Protocol):
    """Role 2, contract section 4."""

    def get_anaf_company(self, cui: str) -> ToolResult: ...
    def get_anaf_financials(self, cui: str, year: int) -> ToolResult: ...
    def get_onrc_company(self, cui: str) -> ToolResult: ...
    def get_court_cases(self, cui: str) -> ToolResult: ...


class ComparisonEngine(Protocol):
    """Role 3, contract section 5: comparison objects, never Findings."""

    def compare(self, fields: list[Field], tool_results: list[ToolResult],
                *, fiscal_year: int) -> list[Any]: ...


class RulesEngine(Protocol):
    """Role 4, contract section 6. The ``app.rules`` module itself satisfies this."""

    def evaluate_rules(self, case_id: str, fields: list[Field], tool_results: list[ToolResult],
                       comparisons: list[Any], documents: list[Document] | None = None) -> list[Finding]: ...
    def rule_catalog(self) -> Catalog: ...


@dataclass(frozen=True)
class VerificationResult:
    case_id: str
    status: Literal["completed", "completed_with_errors", "failed"]
    stages: dict[str, StageStatus]          # inputs, registries, comparisons, rules, outcome
    outcome: Outcome
    tool_results: list[ToolResult] = field(default_factory=list)
    comparisons: list[Any] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)       # evaluated rules only
    not_checked: list[Finding] = field(default_factory=list)    # rules not implemented this sprint
    catalog: Catalog = field(default_factory=list)              # Role 4 rule_catalog()
    errors: list[str] = field(default_factory=list)
    doubles: tuple[str, ...] = ()           # dependencies that were test doubles, not real modules

    @classmethod
    def failed(cls, case_id: str, error: str) -> VerificationResult:
        """The stage itself crashed: no checks ran, so the case escalates (never green)."""
        outcome = decide_outcome(case_id, [], [], [], missing_evidence=True)
        return cls(case_id=case_id, status="failed", stages={}, outcome=outcome, errors=[error])

    def apply_to(self, case: Case) -> Case:
        """Replace, never append, the Sprint 2 parts of a case (reruns are idempotent)."""
        return case.model_copy(update={
            "tool_results": list(self.tool_results),
            "outcome": self.outcome,
            "status": self.outcome.result,     # Outcome and Case status share values
        })


def normalize_cui(value: Any) -> str:
    """Strip whitespace and the optional RO prefix; keep it a string (leading zeros)."""
    text = re.sub(r"\s+", "", str(value)).upper()
    return text[2:] if text.startswith("RO") else text


def read_inputs(documents: list[Document], fields: list[Field]) -> tuple[str | None, int | None, list[str]]:
    """CUI from any verified field, fiscal year from verified balance-sheet fields."""
    errors = []
    cuis = {normalize_cui(f.value) for f in fields
            if f.name == "cui" and f.verified and str(f.value).strip()}
    cui = next(iter(cuis)) if len(cuis) == 1 else None
    if not cuis:
        errors.append("Niciun CUI verificat în documente; registrele nu au fost interogate.")
    elif len(cuis) > 1:
        errors.append(f"CUI-uri diferite în documente: {', '.join(sorted(cuis))}; "
                      "registrele nu au fost interogate.")

    bilant_ids = {d.id for d in documents if d.type == "bilant"}
    years = {f.value for f in fields if f.name == "fiscal_year" and f.verified
             and f.doc_id in bilant_ids and isinstance(f.value, int)}
    year = next(iter(years)) if len(years) == 1 else None
    if not years:
        errors.append("Anul fiscal nu a fost găsit în bilanț.")
    elif len(years) > 1:
        errors.append(f"Ani fiscali diferiți în bilanț: {sorted(years)}.")
    return cui, year, errors


@contextmanager
def _timed(stage: str, case_id: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - start) * 1000
        log.info("verification stage=%s case_id=%s duration_ms=%.1f", stage, case_id, ms,
                 extra={"stage": stage, "case_id": case_id, "duration_ms": ms})


class VerificationOrchestrator:
    def __init__(self, tools: RegistryTools, comparisons: ComparisonEngine, rules: RulesEngine,
                 *, doubles: tuple[str, ...] = ()):
        self.tools = tools
        self.comparisons = comparisons
        self.rules = rules
        self.doubles = doubles

    def run(self, case: Case, fields: list[Field]) -> VerificationResult:
        """One full Sprint 2 pass. Never raises for a teammate-module failure:
        the error is recorded and the outcome escalates instead."""
        errors: list[str] = []
        stages: dict[str, StageStatus] = {}
        tool_results: list[ToolResult] = []
        comparisons: list[Any] = []
        findings: list[Finding] = []
        catalog: Catalog = []

        with _timed("inputs", case.id):
            cui, year, input_errors = read_inputs(case.documents, fields)
            errors += input_errors
            stages["inputs"] = "error" if input_errors else "ok"

        if cui is None:
            stages.update(registries="skipped", comparisons="skipped", rules="skipped")
        else:
            with _timed("registries", case.id):
                before = len(errors)
                tool_results = self._fetch(case.id, cui, year, errors)
                stages["registries"] = "error" if len(errors) > before else "ok"

            with _timed("comparisons", case.id):
                if year is None:
                    stages["comparisons"] = "skipped"     # money needs a fiscal year (contract 5.3)
                else:
                    try:
                        comparisons = list(self.comparisons.compare(fields, tool_results, fiscal_year=year))
                        stages["comparisons"] = "ok"
                    except Exception as exc:
                        log.exception("comparisons failed for case %s", case.id)
                        errors.append(f"comparisons: {exc}")
                        stages["comparisons"] = "error"

            with _timed("rules", case.id):
                try:
                    catalog = list(self.rules.rule_catalog())
                    findings = list(self.rules.evaluate_rules(
                        case.id, fields, tool_results, comparisons, documents=case.documents,
                    ))
                    check_evidence(findings, fields, tool_results, case.documents)
                    stages["rules"] = "ok"
                except Exception as exc:
                    # Includes EvidenceError: findings the UI cannot resolve are not shown.
                    if not isinstance(exc, EvidenceError):
                        log.exception("rules failed for case %s", case.id)
                    errors.append(f"rules: {exc}")
                    findings, catalog = [], []
                    stages["rules"] = "error"
                for rule in missing_mandatory(findings, catalog):
                    errors.append(f"{rule}: regula obligatorie nu are rezultat; tratată ca necunoscută.")
                    stages["rules"] = "error"

        with _timed("outcome", case.id):
            # Any recorded error means a check could not run on full evidence.
            outcome = decide_outcome(case.id, findings, tool_results, catalog,
                                     missing_evidence=bool(errors))
            stages["outcome"] = "ok"

        evaluated, not_checked = split_findings(findings, catalog)
        return VerificationResult(
            case_id=case.id,
            status="completed_with_errors" if errors else "completed",
            stages=stages, outcome=outcome, tool_results=tool_results,
            comparisons=comparisons, findings=evaluated, not_checked=not_checked,
            catalog=catalog, errors=errors, doubles=self.doubles,
        )

    def _fetch(self, case_id: str, cui: str, year: int | None, errors: list[str]) -> list[ToolResult]:
        calls: list[tuple[str, dict[str, Any], Callable[[], ToolResult]]] = [
            ("anaf_company", {"cui": cui}, lambda: self.tools.get_anaf_company(cui)),
            ("onrc_company", {"cui": cui}, lambda: self.tools.get_onrc_company(cui)),
            ("court_cases", {"cui": cui}, lambda: self.tools.get_court_cases(cui)),
        ]
        if year is not None:  # missing year is already an inputs error
            calls.insert(1, ("anaf_financials", {"cui": cui, "year": year},
                             lambda: self.tools.get_anaf_financials(cui, year)))

        results = []
        for name, args, call in calls:
            try:
                results.append(call())
            except Exception as exc:
                log.warning("tool %s failed for case %s: %s", name, case_id, exc)
                errors.append(f"{name}: {exc}")
                results.append(ToolResult(
                    id=f"{case_id}:{name}:unavailable", tool=name, args=args,
                    status="unavailable", data=None, raw_ref=None,
                    fetched_at=datetime.now(timezone.utc),
                ))
        return results
