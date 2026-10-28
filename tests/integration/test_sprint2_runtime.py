"""Minimal cross-role smoke coverage while the Role 6 branch is still empty."""

from pathlib import Path

import pytest

from app.pipeline import run_pipeline


def test_demo02_runs_real_sprint2_chain(monkeypatch):
    pytest.importorskip("pymupdf")
    monkeypatch.setenv("LLM_BACKEND", "replay")
    pdfs = sorted((Path(__file__).resolve().parents[2] / "pdfs" / "DEMO-02").glob("*.pdf"))

    result = run_pipeline("DEMO-02", [(pdf.stem, pdf) for pdf in pdfs])

    assert result.validation["status"] == "completed"
    assert result.validation["doubles"] == []
    assert result.verification.outcome.result == "exceptions"

    comparison = next(item for item in result.verification.comparisons if item["rule_id"] == "R03")
    assert comparison["status"] == "mismatch"
    assert comparison["left"]["value"] == 12_400_000
    assert comparison["right"]["value"] == 8_100_000
    assert comparison["difference"] == 4_300_000
    assert comparison["left"]["evidence"] == ["field:document_3-f11"]
    assert comparison["right"]["evidence"] == ["tool:tool-demo02-financials"]

    finding = next(item for item in result.verification.findings if item.rule_id == "R03")
    assert finding.result == "fail"
    assert finding.severity == "red"
    assert finding.evidence == ["field:document_3-f11", "tool:tool-demo02-financials"]
