"""
app/intake/pdf.py — Interfața din docs/CONTRACT.md pentru branch-ul feat/pdf-processing.

Expune `extract_pages(path) -> list[Page]` (text per page, readable flag), precum și
funcțiile complete din `app.pdf_processing`.
"""
from __future__ import annotations

from app.pdf_processing import (
    DEFAULT_MIN_CHARS_PER_PAGE,
    Page,
    PageExtract,
    ProcessedDocument,
    PromptInjectionFlag,
    extract_page_strings,
    extract_pages,
    extract_text_by_page,
    process_multiple_pdfs,
    process_pdf,
    process_pdf_model,
    render_page_to_png,
    verify_quote_on_page,
)

__all__ = [
    "DEFAULT_MIN_CHARS_PER_PAGE",
    "Page",
    "PageExtract",
    "ProcessedDocument",
    "PromptInjectionFlag",
    "extract_page_strings",
    "extract_pages",
    "extract_text_by_page",
    "process_multiple_pdfs",
    "process_pdf",
    "process_pdf_model",
    "render_page_to_png",
    "verify_quote_on_page",
]

