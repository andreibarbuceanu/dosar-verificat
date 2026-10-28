"""The one place that picks the Sprint 2 dependencies, and the pipeline's
entry point into the verification stage.
"""
from __future__ import annotations

import logging
from typing import Any

from app.models import Case, Document, Field
from app.validation.doubles import NoComparisons, NoRules, UnavailableRegistryTools
from app.validation.orchestrator import RulesEngine, VerificationOrchestrator, VerificationResult

log = logging.getLogger(__name__)


def _rules_engine() -> RulesEngine | None:
    """Role 4's module satisfies RulesEngine as is; None until it is merged."""
    try:
        import app.rules as rules
    except ImportError as exc:
        log.warning("app.rules not importable (%s)", exc)
        return None
    return rules


def build_orchestrator() -> VerificationOrchestrator:
    """Swap each double for the real module as it merges:
    app.tools (Role 2), app.verification (Role 3). app.rules (Role 4) is used
    automatically once it is importable."""
    doubles = ["registry_tools", "comparison_engine"]
    rules = _rules_engine()
    if rules is None:
        rules = NoRules()
        doubles.append("rules_engine")
    log.warning("using test doubles for: %s", ", ".join(doubles))
    return VerificationOrchestrator(
        UnavailableRegistryTools(), NoComparisons(), rules, doubles=tuple(doubles),
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
