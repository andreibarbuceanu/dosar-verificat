"""Rules engine: one Finding per rule R01..R15, deterministic, no model, no clock.

Pure function of its arguments; loading rules.yaml is the only I/O.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.models import Finding

from .config import RULE_IDS, RulesConfigError, load_config
from .definitions import REGISTRY
from .helpers import Context, Verdict, to_dict

if TYPE_CHECKING:  # Role 3 may not be merged yet; never import it at runtime
    from app.models import Document, Field, ToolResult  # noqa: F401


def _deferred(rule_cfg: dict[str, Any]) -> Verdict:
    return Verdict("unknown", f"Neimplementat în Sprint 2: {rule_cfg['deferred_reason_ro']}")


def _run(rule_id: str, rule_cfg: dict[str, Any], ctx: Context) -> Verdict:
    if not rule_cfg["implemented"]:
        return _deferred(rule_cfg)
    rule = REGISTRY.get(rule_id)
    if rule is None:
        raise RulesConfigError(f"{rule_id} is marked implemented in rules.yaml but has no rule function")
    ctx.rule_cfg = rule_cfg
    try:
        return rule(ctx)
    except Exception as exc:  # a broken rule must never become a pass or take the pipeline down
        return Verdict("unknown", f"Eroare internă la evaluarea regulii ({type(exc).__name__}), verificare manuală.")


def _finalize(verdict: Verdict, ctx: Context) -> Verdict:
    """Safety net: evidence must exist in the inputs, and pass/fail must have some."""
    evidence = tuple(ref for ref in verdict.evidence if ctx.resolve(ref) is not None)
    if verdict.result in ("pass", "fail") and not evidence:
        return Verdict("unknown", f"Dovezi insuficiente pentru un rezultat sigur ({verdict.explanation})")
    return Verdict(verdict.result, verdict.explanation, evidence, verdict.severity)


def evaluate_rules(
    case_id: str,
    fields: list[Field],
    tool_results: list[ToolResult],
    comparisons: list[Any],
    documents: list[Document] | None = None,
    config_path: str | None = None,
) -> list[Finding]:
    """Exactly one Finding per rule R01..R15, sorted by rule_id, with stable ids."""
    cfg = load_config(config_path)
    ctx = Context(
        case_id=case_id,
        fields=[to_dict(f) for f in fields or []],
        tools=[to_dict(t) for t in tool_results or []],
        comparisons=[to_dict(c) for c in comparisons or []],
        documents=None if documents is None else [to_dict(d) for d in documents],
    )
    findings = []
    for rule_id in RULE_IDS:
        rule_cfg = cfg["rules"][rule_id]
        verdict = _finalize(_run(rule_id, rule_cfg, ctx), ctx)
        if verdict.severity is not None:
            severity = verdict.severity
        elif verdict.result == "unknown" and rule_cfg["implemented"]:
            severity = cfg["defaults"]["unknown_severity"]
        else:
            severity = rule_cfg["severity"]
        findings.append(Finding(
            id=f"finding-{rule_id}-{case_id}",
            rule_id=rule_id,
            severity=severity,
            result=verdict.result,
            evidence=list(verdict.evidence),
            explanation=verdict.explanation,
            checker="n/a",
        ))
    return findings


def rule_catalog(config_path: str | None = None) -> list[dict[str, Any]]:
    """What each rule is and whether it is evaluated; lets Role 5 tell 'not implemented' from 'evaluated'."""
    cfg = load_config(config_path)
    return [
        {
            "rule_id": rule_id,
            "description": cfg["rules"][rule_id]["description_ro"],
            "severity": cfg["rules"][rule_id]["severity"],
            "implemented": cfg["rules"][rule_id]["implemented"],
            "mandatory": cfg["rules"][rule_id]["mandatory"],
            "inputs": list(cfg["rules"][rule_id]["inputs"]),
            "thresholds": {k: dict(v) for k, v in cfg["rules"][rule_id]["thresholds"].items()},
        }
        for rule_id in RULE_IDS
    ]
