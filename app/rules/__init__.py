"""Deterministic rules engine (Sprint 2, Role 4). See README.md."""
from .config import RulesConfigError
from .engine import evaluate_rules, rule_catalog

__all__ = ["RulesConfigError", "evaluate_rules", "rule_catalog"]
