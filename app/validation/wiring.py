"""The one place that picks the Sprint 2 dependencies, and the pipeline's
entry point into the verification stage.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.models import Case, Document, Field
from app.validation.doubles import NoComparisons, NoRules, UnavailableRegistryTools
from app.validation.orchestrator import RulesEngine, VerificationOrchestrator, VerificationResult

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _VerificationAdapter:
    """Adapt Role 3's flat result model to the shared comparison contract."""

    verification: Any

    @staticmethod
    def _contract_result(result: Any) -> dict[str, Any]:
        refs = list(result.evidence_refs)
        left_ref = next((ref for ref in refs if ref.startswith("field:")), None)
        right_ref = next((ref for ref in refs if ref.startswith("tool:")), None)
        left_evidence = [left_ref] if left_ref else []
        right_evidence = [right_ref] if right_ref else []
        return {
            "check_id": result.check_id,
            "rule_id": result.rule_id,
            "status": result.status,
            "left": {"value": result.left_value, "evidence": left_evidence},
            "right": {"value": result.right_value, "evidence": right_evidence},
            "difference": abs(result.difference) if result.difference is not None else None,
            "explanation": result.explanation,
            "year": result.year,
            "currency": result.currency,
        }

    def compare(self, fields: list[Field], tool_results: list[Any],
                *, fiscal_year: int) -> list[dict[str, Any]]:
        comparisons = [self.verification.compare_pdf_turnover_to_registry(
            fields, tool_results, year=fiscal_year,
        )]
        # R04 is supported by the same deterministic annual-value comparator.
        comparisons.append(self.verification.compare_pdf_financial_to_registry(
            fields, tool_results, field_name="net_profit", year=fiscal_year,
            rule_id="R04", currency="RON",
        ))
        return [self._contract_result(result) for result in comparisons]


def _registry_tools() -> Any | None:
    try:
        import app.tools as tools
    except ImportError as exc:
        log.warning("app.tools not importable (%s)", exc)
        return None
    return tools


def _comparison_engine() -> Any | None:
    try:
        import app.verification as verification
    except ImportError as exc:
        log.warning("app.verification not importable (%s)", exc)
        return None
    return _VerificationAdapter(verification)


def _rules_engine() -> RulesEngine | None:
    """Role 4's module satisfies RulesEngine as is; None until it is merged."""
    try:
        import app.rules as rules
    except ImportError as exc:
        log.warning("app.rules not importable (%s)", exc)
        return None
    return rules


def build_orchestrator() -> VerificationOrchestrator:
    """Use every merged Sprint 2 module and fall back conservatively if absent."""
    doubles = []
    tools = _registry_tools()
    if tools is None:
        tools = UnavailableRegistryTools()
        doubles.append("registry_tools")
    comparisons = _comparison_engine()
    if comparisons is None:
        comparisons = NoComparisons()
        doubles.append("comparison_engine")
    rules = _rules_engine()
    if rules is None:
        rules = NoRules()
        doubles.append("rules_engine")
    if doubles:
        log.warning("using test doubles for: %s", ", ".join(doubles))
    return VerificationOrchestrator(
        tools, comparisons, rules, doubles=tuple(doubles),
    )


def run_verification(case_id: str, documents: list[Document], fields: list[Field],
                     orchestrator: VerificationOrchestrator | None = None) -> VerificationResult:
    """Never raises: an unexpected failure is recorded and the case escalates,
    so the caller keeps its extraction results."""
    try:
        orchestrator = orchestrator or build_orchestrator()
        case = Case(id=case_id, company_name="", cui="", status="running", documents=documents)
        return orchestrator.run(case, fields)
    except Exception as exc:
        log.exception("verification stage failed for case %s", case_id)
        return VerificationResult.failed(case_id, f"verification: {exc}")


def _jsonable(comparison: Any) -> Any:
    """Role 3 comparisons are dataclasses with to_dict(); fakes may be plain dicts."""
    if hasattr(comparison, "to_dict"):
        return comparison.to_dict()
    if hasattr(comparison, "model_dump"):
        return comparison.model_dump(mode="json")
    return comparison


def verification_report(result: VerificationResult) -> dict[str, Any]:
    """The ``validation`` block of GET /cases/{id}/pipeline.

    With doubles no real check ran, so the status says ``not_available`` even
    though an (escalated) outcome exists.
    """
    if result.doubles:
        status = "not_available"
        reason = (f"Verificarea Sprint 2 rulează cu dubluri de test pentru: "
                  f"{', '.join(result.doubles)}. Nu au fost inventate reguli sau date de registru.")
    else:
        status = result.status
        reason = "Registre simulate (fixturi), nu verificări oficiale live."
    return {
        "status": status,
        "result": result.outcome.result,
        "stages": result.stages,
        "errors": result.errors,
        "doubles": list(result.doubles),
        "findings": [f.model_dump(mode="json") for f in result.findings],
        "not_checked": [f.rule_id for f in result.not_checked],
        "comparisons": [_jsonable(c) for c in result.comparisons],
        "reason": reason,
    }
