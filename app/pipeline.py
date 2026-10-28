"""Compatibility pipeline connecting PDF, classification, and extraction modules.

The pipeline intentionally does not read ``companies.json``, ``expected`` or
``planted_errors``.  It sees only the PDF bytes supplied by the caller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Callable

from app.agents.classifier import classify_document
from app.extraction import extract_document
from app.pdf_processing import process_pdf_model


PdfSource = str | Path | bytes | BinaryIO
Complete = Callable[[str, dict], dict]


class PipelineError(RuntimeError):
    """A pipeline stage failed and the caller should return a clear error."""


@dataclass(frozen=True)
class PipelineDocumentResult:
    document_id: str
    file: str
    pages: int
    readable: bool
    document_type: str
    confidence: float
    classification_reason: str
    fields: list[dict[str, Any]] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)
    dropped: list[dict[str, Any]] = field(default_factory=list)
    injection_suspected: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PipelineResult:
    case_id: str
    documents: list[PipelineDocumentResult]
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def process_document(
    source: PdfSource,
    document_id: str,
    *,
    complete: Complete | None = None,
) -> PipelineDocumentResult:
    """Run the real PDF, classifier, and extraction public interfaces."""

    processed = process_pdf_model(source, document_id=document_id)
    if processed.error:
        return PipelineDocumentResult(
            document_id=document_id,
            file=processed.file,
            pages=processed.pages,
            readable=False,
            document_type="unknown",
            confidence=0.0,
            classification_reason="Documentul PDF nu a putut fi procesat.",
            warnings=processed.warnings,
            error=processed.error,
        )

    classification = classify_document(processed.full_text)
    try:
        extraction = extract_document(
            document_id,
            classification.document_type,
            processed.page_strings,
            complete=complete,
        )
    except Exception as exc:
        raise PipelineError(
            f"Extraction failed for {processed.file} ({document_id}): {exc}"
        ) from exc

    warnings = list(processed.warnings)
    if not processed.readable:
        warnings.append("Documentul conține cel puțin o pagină fără text lizibil (R14).")

    return PipelineDocumentResult(
        document_id=document_id,
        file=processed.file,
        pages=processed.pages,
        readable=processed.readable,
        document_type=classification.document_type,
        confidence=classification.confidence,
        classification_reason=classification.reason,
        fields=extraction.fields,
        not_found=extraction.not_found,
        dropped=extraction.dropped,
        injection_suspected=extraction.injection_suspected,
        warnings=warnings,
    )


def run_pipeline(
    case_id: str,
    documents: list[tuple[str, PdfSource]],
    *,
    complete: Complete | None = None,
) -> PipelineResult:
    """Process all documents in a case without consulting ground-truth data."""

    results = [
        process_document(source, document_id, complete=complete)
        for document_id, source in documents
    ]
    return PipelineResult(
        case_id=case_id,
        documents=results,
        validation={
            "status": "not_available",
            "findings": [],
            "reason": (
                "Ramura de validare furnizează evaluatorul offline check_intake.py, "
                "nu un validator runtime pentru un singur dosar. Nu au fost inventate reguli."
            ),
        },
    )
