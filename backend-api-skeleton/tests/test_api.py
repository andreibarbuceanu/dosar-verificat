"""Smoke tests for the API stubs. Run: pytest -q"""
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


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


def test_red_finding_needs_second_approver():
    body = {"action": "confirm", "reason_code": "TURNOVER_MISMATCH", "user": "teo"}
    assert client.post("/findings/x-R03/decision", json=body).status_code == 422
    body["second_approver"] = "stefi"
    assert client.post("/findings/x-R03/decision", json=body).status_code == 201
