"""Focused tests for the integrated PDF -> classify -> extract pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pymupdf")

from app.pipeline import process_document, run_pipeline  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def test_demo02_real_pdfs_run_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "replay")
    pdfs = sorted((ROOT / "pdfs" / "DEMO-02").glob("*.pdf"))

    result = run_pipeline("DEMO-02", [(path.stem, path) for path in pdfs])

    assert [document.document_type for document in result.documents] == [
        "unknown", "application", "bilant", "caf", "onrc"
    ]
    assert all(document.error is None for document in result.documents)
    bilant = next(document for document in result.documents if document.document_type == "bilant")
    turnover = next(field for field in bilant.fields if field["name"] == "turnover")
    assert turnover["value"] == 12_400_000
    assert "12.400.000" in turnover["quote"]
    assert result.validation["status"] == "completed"
    assert result.validation["result"] == "exceptions"
    assert result.validation["doubles"] == []
    json.dumps(result.to_dict(), ensure_ascii=False)


def test_invalid_pdf_is_reported_without_crashing() -> None:
    result = process_document(b"not a PDF", "broken-document")

    assert result.document_type == "unknown"
    assert result.readable is False
    assert result.error
    json.dumps(result.to_dict())
