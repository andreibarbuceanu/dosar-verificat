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
from app.extraction.fallback import deterministic_payload
from app.llm import LLMError
from app.models import Document, Field as EvidenceField
from app.pdf_processing import process_pdf_model
from app.validation import VerificationOrchestrator, VerificationResult
from app.validation.wiring import run_verification, verification_report


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
    fields: list[EvidenceField] = field(default_factory=list)   # ids cited by Finding.evidence
    verification: VerificationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        v = self.verification
        return {
            "case_id": self.case_id,
            "documents": [document.to_dict() for document in self.documents],
            "validation": self.validation,
            "fields": [f.model_dump(mode="json") for f in self.fields],
            "tool_results": [t.model_dump(mode="json") for t in v.tool_results] if v else [],
            "outcome": v.outcome.model_dump(mode="json") if v else None,
        }


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
    except LLMError as exc:
        if "No recorded answer for this prompt" not in str(exc):
            raise PipelineError(
                f"Extraction failed for {processed.file} ({document_id}): {exc}"
            ) from exc
        extraction = extract_document(
            document_id,
            classification.document_type,
            processed.page_strings,
            complete=lambda _prompt, _schema: deterministic_payload(
                classification.document_type, processed.page_strings
            ),
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
    orchestrator: VerificationOrchestrator | None = None,
) -> PipelineResult:
    """Process all documents in a case without consulting ground-truth data,
    then run the Sprint 2 verification stage (which never raises)."""

    results = [
        process_document(source, document_id, complete=complete)
        for document_id, source in documents
    ]
    fields = [
        EvidenceField(id=f"{doc.document_id}-f{index}", **raw)
        for doc in results
        for index, raw in enumerate(doc.fields, start=1)
    ]
    case_documents = [
        Document(id=doc.document_id, type=doc.document_type, file=doc.file,
                 pages=doc.pages, readable=doc.readable)
        for doc in results
    ]
    verification = run_verification(case_id, case_documents, fields, orchestrator)
    return PipelineResult(
        case_id=case_id,
        documents=results,
        validation=verification_report(verification),
        fields=fields,
        verification=verification,
    )
