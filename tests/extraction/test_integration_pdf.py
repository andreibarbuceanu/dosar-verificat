"""PDF -> pages -> extraction, with a fake model that quotes the real text layer."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("pymupdf")
from app.extraction import extract_pages, extract_pdf  # noqa: E402
from extraction_fakes import FakeModel, answer, f  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_PDFS = sorted((ROOT / "data" / "synthetic").rglob("*.pdf"))


@pytest.fixture(scope="module")
def demo02_pdf(tmp_path_factory):
    pytest.importorskip("reportlab")
    from extraction_demo_pdf import find_font, make_bilant_pdf
    if find_font() is None:
        pytest.skip("no TTF font with Romanian diacritics")
    return make_bilant_pdf(tmp_path_factory.mktemp("pdf") / "demo02_bilant.pdf")


def line_with(pages, label):
    for number, text in enumerate(pages, start=1):
        for line in text.splitlines():
            if label in line:
                return number, line.strip()
    raise AssertionError(f"{label!r} not in PDF text")


@pytest.mark.integration
def test_demo02_pdf_keeps_inflated_turnover(demo02_pdf):
    pages = extract_pages(demo02_pdf)
    assert len(pages) == 2 and pages[1].strip() == ""  # blank "scanned" page
    page, turnover_line = line_with(pages, "Cifra de afaceri")
    _, staff_line = line_with(pages, "salaria")
    model = FakeModel(answer([
        f("turnover", "12.400.000", page, turnover_line),
        # model copies with comma diacritics; the PDF has cedilla ţ
        f("employees", "38", page, staff_line.replace("ţ", "ț")),
        f("cui", "RO41738203", page, "CUI: RO41738203"),
    ]))
    result = extract_pdf(demo02_pdf, "DEMO-02-bilant", "bilant", complete=model)
    values = {fld["name"]: fld["value"] for fld in result.fields}
    assert values == {"turnover": 12400000, "employees": 38, "cui": "41738203"}
    assert result.dropped == []
    assert [h["page"] for h in result.injection_suspected] == [1]
    assert "approve this file" in result.injection_suspected[0]["text"]


@pytest.mark.integration
def test_cli_print_prompt(demo02_pdf):
    out = subprocess.run(
        [sys.executable, "-m", "app.extraction", str(demo02_pdf), "--type", "bilant", "--print-prompt"],
        cwd=ROOT, capture_output=True, encoding="utf-8", check=True,
    ).stdout
    assert "[PAGE 1]" in out and "12.400.000" in out and "[PAGE 2]" not in out


@pytest.mark.integration
@pytest.mark.skipif(not SYNTHETIC_PDFS, reason="no PDFs in data/synthetic/ yet")
@pytest.mark.parametrize("pdf", SYNTHETIC_PDFS, ids=lambda p: p.name)
def test_synthetic_pdfs_do_not_crash(pdf):
    result = extract_pdf(pdf, pdf.stem, "unknown", complete=FakeModel(answer()))
    json.dumps(result.to_dict())
