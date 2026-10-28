"""Local-testing helper: per-page text with PyMuPDF. The pipeline gets pages from PDF Processing."""
from __future__ import annotations

from pathlib import Path

from .extract import Complete, ExtractionResult, extract_document


def extract_pages(path: str | Path) -> list[str]:
    try:
        import pymupdf
    except ImportError:  # older PyMuPDF
        import fitz as pymupdf
    with pymupdf.open(str(path)) as doc:
        return [page.get_text("text") for page in doc]


def extract_pdf(path: str | Path, doc_id: str, doc_type: str,
                complete: Complete | None = None) -> ExtractionResult:
    return extract_document(doc_id, doc_type, extract_pages(path), complete=complete)
