"""Public data models for document classification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Literal, Union


DocumentType = Literal["application", "bilant", "onrc", "caf", "ubo", "unknown"]


@dataclass(frozen=True)
class ClassificationResult:
    """Stable result returned by :func:`classify_document`.

    ``confidence`` is a deterministic heuristic score, not a calibrated
    probability.
    """

    document_type: DocumentType
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def to_dict(self) -> Dict[str, Union[str, float]]:
        """Return a JSON-serializable representation."""

        return asdict(self)
