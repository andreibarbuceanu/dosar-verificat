"""Loads and validates rules.yaml. This is the only I/O the engine does."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).with_name("rules.yaml")
RULE_IDS = tuple(f"R{i:02d}" for i in range(1, 16))
SEVERITIES = ("red", "amber", "info")

_TOP_KEYS = {"version", "defaults", "rules"}
_RULE_KEYS = {
    "description_ro", "severity", "implemented", "mandatory", "inputs", "thresholds",
    "deferred_reason_ro",
}
_THRESHOLD_KEYS = {"value", "source", "confirmed"}

# Thresholds the rule code reads; a missing one must fail at load time, not mid-evaluation.
REQUIRED_THRESHOLDS: dict[str, set[str]] = {
    "R02": {"non_cui_mismatch_severity", "cui_check_id_markers"},
    "R03": {"tolerance_abs", "currency"},
    "R04": {"tolerance_abs", "currency"},
    "R05": {"tolerance_abs", "currency"},
    "R07": {"window_months"},
    "R08": {"max_age_days"},
    "R11": {"min_percent"},
    "R13": {
        "insolvency_keywords", "enforcement_keywords", "debtor_roles", "open_statuses",
        "closed_statuses", "insolvency_severity", "enforcement_severity", "name_similarity_min",
    },
    "R14": {"required_document_types"},
}


class RulesConfigError(ValueError):
    """rules.yaml is malformed."""


def _fail(path: Path, message: str) -> None:
    raise RulesConfigError(f"{path}: {message}")


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    try:
        with open(cfg_path, encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except OSError as exc:
        raise RulesConfigError(f"{cfg_path}: cannot read rules file ({exc})") from exc
    except yaml.YAMLError as exc:
        raise RulesConfigError(f"{cfg_path}: invalid YAML ({exc})") from exc
    return _validate(raw, cfg_path)


def _validate(raw: Any, path: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        _fail(path, "top level must be a mapping")
    unknown = set(raw) - _TOP_KEYS
    if unknown:
        _fail(path, f"unknown top-level keys: {sorted(unknown)}")

    defaults = raw.get("defaults")
    if not isinstance(defaults, dict) or defaults.get("unknown_severity") not in SEVERITIES:
        _fail(path, "defaults.unknown_severity must be one of red|amber|info")

    rules = raw.get("rules")
    if not isinstance(rules, dict):
        _fail(path, "'rules' must be a mapping")
    missing = [r for r in RULE_IDS if r not in rules]
    if missing:
        _fail(path, f"missing rules: {missing}")
    extra = sorted(set(rules) - set(RULE_IDS))
    if extra:
        _fail(path, f"unknown rule ids: {extra}")

    for rule_id in RULE_IDS:
        _validate_rule(rule_id, rules[rule_id], path)
    return raw


def _validate_rule(rule_id: str, rule: Any, path: Path) -> None:
    where = f"rule {rule_id}"
    if not isinstance(rule, dict):
        _fail(path, f"{where} must be a mapping")
    unknown = set(rule) - _RULE_KEYS
    if unknown:
        _fail(path, f"{where}: unknown keys {sorted(unknown)}")
    for key in ("description_ro", "severity", "implemented", "mandatory", "inputs", "thresholds"):
        if key not in rule:
            _fail(path, f"{where}: missing '{key}'")
    if not isinstance(rule["description_ro"], str) or not rule["description_ro"].strip():
        _fail(path, f"{where}: description_ro must be a non-empty string")
    if rule["severity"] not in SEVERITIES:
        _fail(path, f"{where}: severity must be one of {SEVERITIES}, got {rule['severity']!r}")
    for key in ("implemented", "mandatory"):
        if not isinstance(rule[key], bool):
            _fail(path, f"{where}: {key} must be true or false")
    if not isinstance(rule["inputs"], list) or not all(isinstance(i, str) for i in rule["inputs"]):
        _fail(path, f"{where}: inputs must be a list of strings")
    if not rule["implemented"] and not str(rule.get("deferred_reason_ro", "")).strip():
        _fail(path, f"{where}: an unimplemented rule needs deferred_reason_ro")

    thresholds = rule["thresholds"]
    if not isinstance(thresholds, dict):
        _fail(path, f"{where}: thresholds must be a mapping")
    for name, item in thresholds.items():
        if not isinstance(item, dict) or set(item) != _THRESHOLD_KEYS:
            _fail(path, f"{where}: threshold '{name}' needs exactly value, source, confirmed")
        if not isinstance(item["source"], str) or not item["source"].strip():
            _fail(path, f"{where}: threshold '{name}' needs a source")
        if not isinstance(item["confirmed"], bool):
            _fail(path, f"{where}: threshold '{name}': confirmed must be true or false")
    lacking = REQUIRED_THRESHOLDS.get(rule_id, set()) - set(thresholds)
    if lacking:
        _fail(path, f"{where}: missing thresholds {sorted(lacking)}")
    for name in ("non_cui_mismatch_severity", "insolvency_severity", "enforcement_severity"):
        if name in thresholds and thresholds[name]["value"] not in SEVERITIES:
            _fail(path, f"{where}: threshold '{name}' must be one of {SEVERITIES}")
