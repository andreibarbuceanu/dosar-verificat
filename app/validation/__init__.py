"""Sprint 2 outcome orchestration (Role 5). See docs/SPRINT2_CONTRACT.md section 7."""
from app.validation.orchestrator import (
    ComparisonEngine,
    RegistryTools,
    RulesEngine,
    VerificationOrchestrator,
    VerificationResult,
    normalize_cui,
    read_inputs,
)
from app.validation.outcome import (
    LITIGATION_SCORE_NOT_COMPUTED,
    EvidenceError,
    check_evidence,
    decide_outcome,
    mandatory_rules,
    missing_mandatory,
    split_findings,
)

__all__ = [
    "LITIGATION_SCORE_NOT_COMPUTED",
    "ComparisonEngine",
    "EvidenceError",
    "RegistryTools",
    "RulesEngine",
    "VerificationOrchestrator",
    "VerificationResult",
    "check_evidence",
    "decide_outcome",
    "mandatory_rules",
    "missing_mandatory",
    "normalize_cui",
    "read_inputs",
    "split_findings",
]
