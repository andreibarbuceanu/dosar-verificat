from pathlib import Path

import pytest

pytest.importorskip("pymupdf")

from app.pipeline import run_pipeline


def test_unrecorded_demo01_uses_conservative_deterministic_fallback(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "replay")
    root = Path(__file__).resolve().parents[2]
    pdfs = sorted((root / "pdfs" / "DEMO-01").glob("*.pdf"))

    result = run_pipeline("DEMO-01-FALLBACK", [(pdf.stem, pdf) for pdf in pdfs])

    assert [document.document_type for document in result.documents] == [
        "onrc", "caf", "bilant", "application", "ubo"
    ]
    assert all(document.error is None for document in result.documents)
    assert {field.value for field in result.fields if field.name == "cui"} == {"36182043"}
    assert next(field.value for field in result.fields if field.name == "turnover") == 4_650_000
    assert next(field.value for field in result.fields if field.name == "requested_amount") == 900_000
