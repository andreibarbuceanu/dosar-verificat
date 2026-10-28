"""Real DEMO-02 PDFs through pipeline and API, with Role 2-4 fakes.

The registry fake answers for whatever CUI the PDFs carry; its values are
written here, not read from companies.json / expected / planted_errors.
"""
from __future__ import annotations

import builtins
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("pymupdf")

import app.api.main as api  # noqa: E402
import app.validation.wiring as wiring  # noqa: E402
from app.pipeline import run_pipeline  # noqa: E402
from tests.validation.fakes import FakeRegistryTools, court, financials, orchestrator  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PDFS = sorted((ROOT / "pdfs" / "DEMO-02").glob("*.pdf"))
FORBIDDEN = ("companies.json", "expected", "planted_errors", "ground_truth")


def demo_registry() -> FakeRegistryTools:
    # The fake ignores the CUI it is asked for; real tools look it up.
    return FakeRegistryTools({"anaf_company": {"active": True},
                         "anaf_financials": financials("any", 8_100_000),
                         "onrc_company": {"name": "AGRO NORD TRANS SRL"},
                         "court_cases": court("any")})


@pytest.fixture(autouse=True)
def replay_llm(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "replay")


def test_demo02_turnover_mismatch_gives_runtime_r03_exception():
    registry = demo_registry()
    result = run_pipeline("DEMO-02", [(p.stem, p) for p in PDFS], orchestrator=orchestrator(registry))

    [(_, cui, year)] = [c for c in registry.calls if c[0] == "anaf_financials"]
    assert year == 2024 and cui.isdigit()
    assert result.validation["status"] == "completed"
    assert result.validation["errors"] == []
    assert result.validation["comparisons"][0]["difference"] == 4_300_000

    v = result.verification
    outcome = v.outcome
    assert outcome.result == "exceptions"
    [r03] = [f for f in outcome.findings if f.rule_id == "R03"]
    assert r03.result == "fail" and r03.severity == "red" and r03.checker == "n/a"

    fields = {f"field:{f.id}": f for f in result.fields}
    tools = {f"tool:{t.id}": t for t in v.tool_results}
    turnover, registry_answer = (fields.get(r03.evidence[0]), tools.get(r03.evidence[1]))
    assert turnover.name == "turnover" and turnover.value == 12_400_000
    assert registry_answer.tool == "anaf_financials"
    assert outcome.litigation_score == 100 and outcome.deductions == []
    json.dumps(result.to_dict(), ensure_ascii=False)


def test_default_wiring_runs_all_integrated_modules():
    result = run_pipeline("DEMO-02", [(p.stem, p) for p in PDFS])
    assert result.validation["status"] == "completed"
    assert result.validation["doubles"] == []
    assert result.verification.outcome.result == "exceptions"
    assert {t.status for t in result.verification.tool_results} == {"ok"}
    r03 = next(f for f in result.verification.findings if f.rule_id == "R03")
    assert r03.result == "fail"
    assert any(f.name == "turnover" for f in result.fields)


def test_runtime_never_opens_ground_truth(monkeypatch):
    opened: list[str] = []
    real_open = io.open

    def spy(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    run_pipeline("DEMO-02", [(p.stem, p) for p in PDFS], orchestrator=orchestrator(demo_registry()))

    assert opened, "spy saw no file opens; the check would be vacuous"
    assert not [p for p in opened if any(word in p for word in FORBIDDEN)]


def test_api_run_sets_outcome_status_and_queue_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(wiring, "build_orchestrator", lambda: orchestrator(demo_registry()))
    client = TestClient(api.app)

    files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in PDFS]
    case_id = client.post("/cases", files=files).json()["id"]
    case = client.post(f"/cases/{case_id}/run").json()

    assert case["status"] == "exceptions"
    assert case["outcome"]["result"] == "exceptions"
    refs = {f"field:{f['id']}" for f in case["fields"]} | {f"tool:{t['id']}" for t in case["tool_results"]}
    for finding in case["outcome"]["findings"]:
        assert set(finding["evidence"]) <= refs

    row = next(r for r in client.get("/cases").json() if r["id"] == case_id)
    assert (row["status"], row["red"]) == ("exceptions", 1)
    report = client.get(f"/cases/{case_id}/pipeline").json()
    assert report["validation"]["status"] == "completed"
    assert report["validation"]["result"] == "exceptions"

    r03_id = next(f["id"] for f in case["outcome"]["findings"] if f["rule_id"] == "R03")
    body = {"action": "confirm", "reason_code": "TURNOVER_MISMATCH", "user": "a", "second_approver": "b"}
    assert client.post(f"/findings/{r03_id}/decision", json=body).status_code == 201


def test_demo02_with_real_rules_engine_when_merged():
    """Runs only once Role 4's app.rules is on the branch: real rules + catalog."""
    rules = pytest.importorskip("app.rules")
    from app.validation import VerificationOrchestrator
    from tests.validation.fakes import FakeComparisonEngine

    orch = VerificationOrchestrator(demo_registry(), FakeComparisonEngine(), rules)
    result = run_pipeline("DEMO-02", [(p.stem, p) for p in PDFS], orchestrator=orch).verification

    assert result.stages["rules"] == "ok"
    r03 = next(f for f in result.findings if f.rule_id == "R03")
    assert (r03.result, r03.severity) == ("fail", "red")
    assert result.outcome.result == "exceptions"
    assert "R12" in [f.rule_id for f in result.not_checked]
    assert "R12" not in [f.rule_id for f in result.outcome.findings]
