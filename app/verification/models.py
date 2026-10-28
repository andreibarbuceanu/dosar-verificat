"""Models owned by the standalone cross-document verification module."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ComparisonStatus = Literal["match", "mismatch", "unknown"]


@dataclass(frozen=True)
class ComparisonResult:
    """A comparison only; it is deliberately not a rule-engine Finding."""

    check_id: str
    rule_id: str
    status: ComparisonStatus
    left_value: Any
    right_value: Any
    evidence_refs: list[str] = field(default_factory=list)
    explanation: str = ""
    difference: int | float | None = None
    currency: str | None = None
    year: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""

        return asdict(self)
