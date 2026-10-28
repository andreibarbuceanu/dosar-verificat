"""Sprint 2 API additions are backward compatible (TestClient, real DEMO-02 PDFs)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("pymupdf")

import app.api.main as api  # noqa: E402
import app.validation.wiring as wiring  # noqa: E402
from app.api.main import tool_source  # noqa: E402
from app.models import Case, CaseSummary  # noqa: E402
from tests.validation.fakes import FakeRegistryTools, court, financials, orchestrator  # noqa: E402

PDFS = sorted((Path(__file__).resolve().parents[2] / "pdfs" / "DEMO-02").glob("*.pdf"))
CASE_KEYS = set(Case.model_fields)
SUMMARY_KEYS = set(CaseSummary.model_fields)
client = TestClient(api.app)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "replay")
    monkeypatch.setattr(api, "UPLOADS", tmp_path / "uploads")


def fake_registry() -> FakeRegistryTools:
    return FakeRegistryTools({"anaf_company": {"active": True},
                              "anaf_financials": financials("any", 8_100_000),
                              "onrc_company": {"name": "AGRO NORD TRANS SRL"},
                              "court_cases": court("any")})


def upload() -> str:
    files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in PDFS]
    return client.post("/cases", files=files).json()["id"]


def run_with_fakes(monkeypatch) -> tuple[str, dict]:
    monkeypatch.setattr(wiring, "build_orchestrator", lambda: orchestrator(fake_registry()))
    case_id = upload()
    run = client.post(f"/cases/{case_id}/run")
    assert run.status_code == 200
    return case_id, run.json()


# ---------- old response fields unchanged ----------

def test_existing_shapes_are_unchanged_before_and_after_a_run(monkeypatch):
    assert all(set(row) == SUMMARY_KEYS for row in client.get("/cases").json())
    assert set(client.get("/cases/DEMO-02").json()) == CASE_KEYS

    case_id, ran = run_with_fakes(monkeypatch)
    assert set(ran) == CASE_KEYS
    assert set(client.get(f"/cases/{case_id}").json()) == CASE_KEYS
    assert all(set(row) == SUMMARY_KEYS for row in client.get("/cases").json())
    pipeline = client.get(f"/cases/{case_id}/pipeline").json()
    assert {"case_id", "documents", "validation"} <= set(pipeline)
    assert {"status", "findings", "reason"} <= set(pipeline["validation"])


def test_seeded_fixture_case_is_untouched():
    case = client.get("/cases/DEMO-02").json()
    assert case["status"] == "exceptions" and case["outcome"]["litigation_score"] == 80


# ---------- new fields after a run ----------

def test_case_carries_tool_results_and_outcome_after_run(monkeypatch):
    case_id, _ = run_with_fakes(monkeypatch)
    case = client.get(f"/cases/{case_id}").json()

    assert case["status"] == case["outcome"]["result"] == "exceptions"
    assert len(case["tool_results"]) == 4
    assert [f["rule_id"] for f in case["outcome"]["findings"]] == ["R03", "R04", "R13"]  # no R12
    row = next(r for r in client.get("/cases").json() if r["id"] == case_id)
    assert row["status"] == case["outcome"]["result"]          # queue shows the outcome
    assert (row["red"], row["amber"]) == (1, 0)


def test_verification_endpoint_returns_stage_details(monkeypatch):
    case_id, _ = run_with_fakes(monkeypatch)
    body = client.get(f"/cases/{case_id}/verification").json()

    assert body["status"] == "completed" and body["errors"] == [] and body["doubles"] == []
    assert body["stages"] == {"inputs": "ok", "registries": "ok", "comparisons": "ok",
                              "rules": "ok", "outcome": "ok"}
    assert {t["tool"] for t in body["tool_results"]} == {
        "anaf_company", "anaf_financials", "onrc_company", "court_cases"}
    assert all("raw_ref" in t and t["source"] in ("fixture", "live", "unknown")
               for t in body["tool_results"])
    assert body["comparisons"][0]["difference"] == 4_300_000
    assert body["findings"] == body["outcome"]["findings"]
    assert [f["rule_id"] for f in body["not_checked"]] == ["R12"]
    assert body["not_checked"][0]["explanation"].startswith("Neimplementat în Sprint 2:")
    assert {r["rule_id"] for r in body["rule_catalog"]} == {"R03", "R04", "R12", "R13"}
    assert body["outcome"]["result"] == "exceptions"
    assert body["litigation_score_status"] == "not_computed"


def test_default_wiring_exposes_real_integrated_results():
    case_id = upload()
    assert client.post(f"/cases/{case_id}/run").json()["status"] == "exceptions"
    body = client.get(f"/cases/{case_id}/verification").json()
    assert body["status"] == "completed"
    assert body["doubles"] == []
    assert {t["status"] for t in body["tool_results"]} == {"ok"}
    assert {t["source"] for t in body["tool_results"]} == {"fixture"}
    assert next(f for f in body["findings"] if f["rule_id"] == "R03")["result"] == "fail"


@pytest.mark.parametrize("raw_ref, source", [
    ("fixtures/registry/DEMO-02/anaf_financials.json", "fixture"),
    ("fixtures\\registry\\DEMO-02\\onrc.json", "fixture"),
    ("https://example.invalid/anaf", "unknown"),
    (None, "unknown"),
])
def test_tool_source_never_claims_live(raw_ref, source):
    assert tool_source(raw_ref) == source


# ---------- errors ----------

@pytest.mark.parametrize("path", ["/cases/NOPE", "/cases/NOPE/verification", "/cases/NOPE/pipeline"])
def test_unknown_case_is_404(path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json()["detail"] == "Case NOPE not found"


def test_verification_before_run_is_a_readable_409():
    case_id = upload()
    response = client.get(f"/cases/{case_id}/verification")
    assert response.status_code == 409
    assert response.json()["detail"] == (
        f"Verification has not run for case {case_id}; call POST /cases/{case_id}/run first")


def test_seeded_case_has_no_runtime_verification():
    assert client.get("/cases/DEMO-02/verification").status_code == 409
