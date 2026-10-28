"""API and integrated-pipeline tests. Run: pytest -q"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.api.main as api
from app.api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def uploads_in_tmp(tmp_path, monkeypatch):
    """Point uploads at a temp folder so tests never write into the repo."""
    monkeypatch.setattr(api, "UPLOADS", tmp_path / "uploads")


def test_health():
    assert client.get("/health").json()["api"] == "ok"


def test_queue_contains_demo02_with_counts():
    rows = {r["id"]: r for r in client.get("/cases").json()}
    assert rows["DEMO-02"]["status"] == "exceptions"
    assert rows["DEMO-02"]["red"] == 1      # R03
    assert rows["DEMO-02"]["amber"] == 1    # R13


def test_case_has_evidence_for_r03():
    case = client.get("/cases/DEMO-02").json()
    r03 = next(f for f in case["outcome"]["findings"] if f["rule_id"] == "R03")
    assert r03["result"] == "fail" and "field:f6" in r03["evidence"]


def test_upload_creates_new_case():
    files = [("files", ("bilant.pdf", b"%PDF-1.4 fake", "application/pdf"))]
    r = client.post("/cases", files=files)
    assert r.status_code == 201 and r.json()["status"] == "new"


def test_upload_rejects_non_pdf():
    files = [("files", ("notes.txt", b"hello", "text/plain"))]
    assert client.post("/cases", files=files).status_code == 400


def test_rejected_upload_writes_nothing():
    files = [("files", ("bilant.pdf", b"%PDF-1.4 fake", "application/pdf")),
             ("files", ("notes.txt", b"hello", "text/plain"))]
    assert client.post("/cases", files=files).status_code == 400
    assert not api.UPLOADS.exists()


def test_red_finding_needs_second_approver():
    body = {"action": "confirm", "reason_code": "TURNOVER_MISMATCH", "user": "teo"}
    assert client.post("/findings/x-R03/decision", json=body).status_code == 422
    body["second_approver"] = "stefi"
    assert client.post("/findings/x-R03/decision", json=body).status_code == 201


def test_uploaded_demo02_runs_real_pipeline(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "replay")
    root = Path(__file__).resolve().parents[1]
    pdfs = sorted((root / "pdfs" / "DEMO-02").glob("*.pdf"))
    files = [("files", (path.name, path.read_bytes(), "application/pdf")) for path in pdfs]

    created = client.post("/cases", files=files)
    assert created.status_code == 201
    case_id = created.json()["id"]

    run = client.post(f"/cases/{case_id}/run")
    assert run.status_code == 200
    payload = run.json()
    assert [document["type"] for document in payload["documents"]] == [
        "ubo", "application", "bilant", "caf", "onrc"
    ]
    turnover = next(field for field in payload["fields"] if field["name"] == "turnover")
    assert turnover["value"] == 12_400_000

    report = client.get(f"/cases/{case_id}/pipeline")
    assert report.status_code == 200
    validation = report.json()["validation"]
    assert validation["status"] == "completed"
    assert validation["result"] == "exceptions"
    assert validation["doubles"] == []

    bilant_id = payload["documents"][2]["id"]
    page = client.get(f"/documents/{bilant_id}/pages/2")
    assert page.status_code == 200
    assert page.headers["content-type"] == "image/png"
    assert page.content.startswith(b"\x89PNG\r\n\x1a\n")
