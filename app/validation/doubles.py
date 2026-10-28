"""Runtime stand-ins for Roles 2-4 until their modules are merged.

They invent nothing (contract principle 3): every registry answers
``unavailable``, there are no comparisons and no findings, so a case run with
them always escalates and is never green.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import Document, Field, Finding, ToolResult


class UnavailableRegistryTools:
    def _unavailable(self, tool: str, args: dict[str, Any]) -> ToolResult:
        suffix = "-".join(str(v) for v in args.values())
        return ToolResult(id=f"double:{tool}:{suffix}", tool=tool, args=args,
                          status="unavailable", data=None, raw_ref=None,
                          fetched_at=datetime.now(timezone.utc))

    def get_anaf_company(self, cui: str) -> ToolResult:
        return self._unavailable("anaf_company", {"cui": cui})

    def get_anaf_financials(self, cui: str, year: int) -> ToolResult:
        return self._unavailable("anaf_financials", {"cui": cui, "year": year})

    def get_onrc_company(self, cui: str) -> ToolResult:
        return self._unavailable("onrc_company", {"cui": cui})

    def get_court_cases(self, cui: str) -> ToolResult:
        return self._unavailable("court_cases", {"cui": cui})


class NoComparisons:
    def compare(self, fields: list[Field], tool_results: list[ToolResult],
                *, fiscal_year: int) -> list[Any]:
        return []


class NoRules:
    """No catalog means no mandatory rule, so the outcome can never be green."""

    def evaluate_rules(self, case_id: str, fields: list[Field], tool_results: list[ToolResult],
                       comparisons: list[Any], documents: list[Document] | None = None) -> list[Finding]:
        return []

    def rule_catalog(self) -> list[dict[str, Any]]:
        return []
