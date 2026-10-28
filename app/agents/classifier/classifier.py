"""Deterministic Romanian banking-document classifier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, cast

from .indicators import INDICATORS
from .models import ClassificationResult, DocumentType
from .normalization import normalize_text


_MIN_SCORE = 6.0
_MIN_DISTINCT_INDICATORS = 2
_AMBIGUITY_RATIO = 0.72

_REASONS = {
    "application": "Documentul conține formulări specifice unei cereri de credit și condițiilor finanțării.",
    "bilant": "Documentul conține indicatori specifici bilanțului și situațiilor financiare anuale.",
    "onrc": "Documentul conține elemente specifice unui certificat constatator emis de Registrul Comerțului.",
    "caf": "Documentul conține elemente specifice unui certificat de atestare fiscală și obligațiilor fiscale.",
}


@dataclass(frozen=True)
class _CategoryScore:
    score: float
    matches: Tuple[str, ...]


def _score_categories(normalized: str) -> Dict[str, _CategoryScore]:
    scores: Dict[str, _CategoryScore] = {}
    padded_text = f" {normalized} "
    for category, indicators in INDICATORS.items():
        matched: List[str] = []
        score = 0.0
        # Prefer the most specific phrase and avoid counting a shorter phrase
        # nested inside it as independent evidence.
        for phrase, weight in sorted(indicators, key=lambda item: len(item[0]), reverse=True):
            if f" {phrase} " in padded_text:
                if any(phrase in existing for existing in matched):
                    continue
                matched.append(phrase)
                score += weight
        scores[category] = _CategoryScore(score=score, matches=tuple(matched))
    return scores


def _confidence(score: float, runner_up: float, match_count: int) -> float:
    """Map evidence and separation to a bounded heuristic confidence score."""

    evidence = min(score / 15.0, 1.0)
    separation = 1.0 if score == 0 else max(0.0, (score - runner_up) / score)
    diversity = min(match_count / 4.0, 1.0)
    return round(min(0.99, 0.45 + 0.30 * evidence + 0.15 * separation + 0.10 * diversity), 2)


def classify_document(text: str) -> ClassificationResult:
    """Classify extracted document text using deterministic weighted evidence.

    The function does not read files, fixtures, or external services. Its
    confidence value is a heuristic score and must not be interpreted as a
    calibrated probability.
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    normalized = normalize_text(text)
    if not normalized:
        return ClassificationResult(
            document_type="unknown",
            confidence=0.0,
            reason="Textul documentului este gol sau conține doar spații.",
        )

    scores = _score_categories(normalized)
    ranking = sorted(scores.items(), key=lambda item: item[1].score, reverse=True)
    (winner, best), (runner_up, second) = ranking[:2]

    if best.score < _MIN_SCORE or len(best.matches) < _MIN_DISTINCT_INDICATORS:
        return ClassificationResult(
            document_type="unknown",
            confidence=round(min(0.49, best.score / 15.0), 2),
            reason="Textul nu conține suficiente indicii document-specifice pentru o clasificare sigură.",
        )

    if second.score >= _MIN_SCORE and second.score / best.score >= _AMBIGUITY_RATIO:
        return ClassificationResult(
            document_type="unknown",
            confidence=0.5,
            reason=(
                "Textul este ambiguu: conține indicii comparabile pentru "
                f"categoriile {winner} și {runner_up}."
            ),
        )

    document_type = cast(DocumentType, winner)
    return ClassificationResult(
        document_type=document_type,
        confidence=_confidence(best.score, second.score, len(best.matches)),
        reason=_REASONS[winner],
    )
