"""HTTP API from ``docs/CONTRACT.md``.

Uploaded cases run the integrated PDF -> classification -> extraction flow,
then the Sprint 2 verification stage (simulated registries, comparisons, rules,
outcome). Seeded fixture cases remain available for frontend development.
While that stage runs on test doubles, validation is reported as not available
and the case escalates; nothing is invented.

Run:  uvicorn app.api.main:app --reload      ->  http://localhost:8000/docs

Java comparison: `app` is the Spring Boot application, each @app.get is a
@GetMapping on a @RestController, and `response_model=` is the return DTO that
FastAPI validates and serialises for you.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from app.models import AuditLine, Case, CaseSummary, Decision, Document, Finding, Outcome, ToolResult
from app.pdf_processing import render_page_to_png
from app.pipeline import PipelineError, run_pipeline
from app.validation import VerificationResult
from app.validation.wiring import verification_report

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "api"
# Runtime storage for uploaded PDFs, not test data and not in git (data/ belongs to the data team).
UPLOADS = ROOT / "storage" / "uploads"

app = FastAPI(title="Dosar Verificat API", version="0.1.0")

# The Vite dev server runs on another port, so the browser needs CORS allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- in-memory store (enough for a hackathon; a DB is not scored) ----------
CASES: dict[str, Case] = {}
DECISIONS: list[Decision] = []
PIPELINE_RESULTS: dict[str, dict] = {}
VERIFICATIONS: dict[str, VerificationResult] = {}


def _load_fixtures() -> None:
    """Seed the store with every fixtures/api/case_*.json. Validation runs here,
    so a broken fixture stops the server at startup instead of in the demo."""
    for path in sorted(FIXTURES.glob("case_*.json")):
        case = Case.model_validate_json(path.read_text(encoding="utf-8"))
        CASES[case.id] = case


_load_fixtures()


def _get_case(case_id: str) -> Case:
    if case_id not in CASES:
        raise HTTPException(404, f"Case {case_id} not found")
    return CASES[case_id]


# ---------- endpoints ----------
@app.get("/health")
def health() -> dict:
    # Registry connectivity is outside Sprint 1.
    return {"api": "ok", "registries": {"anaf": "unknown", "sanctions": "unknown", "court": "unknown"}}


@app.get("/cases", response_model=list[CaseSummary])
def list_cases() -> list[CaseSummary]:
    rows = []
    for c in CASES.values():
        findings = c.outcome.findings if c.outcome else []
        fails = [f for f in findings if f.result == "fail"]
        rows.append(CaseSummary(
            id=c.id, company_name=c.company_name, status=c.status,
            red=sum(f.severity == "red" for f in fails),
            amber=sum(f.severity == "amber" for f in fails),
        ))
    return rows


@app.post("/cases", response_model=Case, status_code=201)
async def create_case(files: list[UploadFile] = File(...)) -> Case:
    """Upload a credit file's PDFs. Saves them; classification happens on /run."""
    # Validate every file first, so a rejected upload leaves nothing on disk.
    for f in files:
        if not (f.filename or "").lower().endswith(".pdf"):
            raise HTTPException(400, f"{f.filename}: only PDF files are accepted")

    case_id = f"C-{uuid.uuid4().hex[:8]}"
    folder = UPLOADS / case_id
    folder.mkdir(parents=True, exist_ok=True)

    docs = []
    for i, f in enumerate(files, start=1):
        safe_name = Path(f.filename or "").name
        if not safe_name:
            raise HTTPException(400, "Every upload must have a file name")
        (folder / safe_name).write_bytes(await f.read())
        # type/pages are placeholders until PDF Processing and Classification run.
        docs.append(Document(id=f"{case_id}-d{i}", type="unknown", file=safe_name, pages=0))

    case = Case(id=case_id, company_name="", cui="", status="new", documents=docs)
    CASES[case_id] = case
    return case


@app.post("/cases/{case_id}/run", response_model=Case)
def run_case(case_id: str) -> Case:
    case = _get_case(case_id)
    if case.outcome is not None:
        return case

    sources = [(doc.id, UPLOADS / case_id / doc.file) for doc in case.documents]
    try:
        # Sprint 2 dependencies are chosen in app.validation.wiring.build_orchestrator().
        result = run_pipeline(case_id, sources)
    except PipelineError as exc:
        raise HTTPException(503, str(exc)) from exc

    broken = [doc for doc in result.documents if doc.error]
    if broken:
        details = "; ".join(f"{doc.file}: {doc.error}" for doc in broken)
        raise HTTPException(422, f"One or more PDFs could not be processed: {details}")

    case.documents = [
        Document(
            id=doc.document_id,
            type=doc.document_type,
            file=doc.file,
            pages=doc.pages,
            readable=doc.readable,
        )
        for doc in result.documents
    ]
    case.fields = result.fields
    company = next((f.value for f in case.fields if f.name == "company_name"), None)
    cui = next((f.value for f in case.fields if f.name == "cui"), None)
    if isinstance(company, str):
        case.company_name = company
    if isinstance(cui, str):
        case.cui = cui
    case = result.verification.apply_to(case)   # replaces tool_results/outcome/status
    CASES[case_id] = case
    PIPELINE_RESULTS[case_id] = result.to_dict()
    VERIFICATIONS[case_id] = result.verification
    return case


@app.get("/cases/{case_id}/pipeline")
def get_pipeline_result(case_id: str) -> dict:
    _get_case(case_id)
    if case_id not in PIPELINE_RESULTS:
        raise HTTPException(404, f"Pipeline has not run for case {case_id}")
    return PIPELINE_RESULTS[case_id]


# ---------- Sprint 2 verification view ----------
# Case and its nested models are extra="forbid" and coordinator-owned
# (SPRINT2_CONTRACT 2, 7.2), so the extra Sprint 2 details live in their own
# response instead of new keys on GET /cases/{id}.
ToolSource = Literal["fixture", "live", "unknown"]


def tool_source(raw_ref: str | None) -> ToolSource:
    """Sprint 2 has no live provider: a raw_ref under fixtures/ is a fixture,
    anything else is unknown. "live" is reserved for a future live provider."""
    if raw_ref and raw_ref.replace("\\", "/").startswith("fixtures/"):
        return "fixture"
    return "unknown"


class ToolResultOut(ToolResult):
    source: ToolSource


class VerificationOut(BaseModel):
    case_id: str
    status: Literal["completed", "completed_with_errors", "failed", "not_available"]
    stages: dict[str, Literal["ok", "error", "skipped"]]
    errors: list[str]
    doubles: list[str]                      # Sprint 2 modules still replaced by test doubles
    tool_results: list[ToolResultOut]
    comparisons: list[dict[str, Any]]
    findings: list[Finding]                 # evaluated rules (same as outcome.findings)
    # Rules not implemented this sprint ("neverificat"): never pass, never block green.
    not_checked: list[Finding]
    rule_catalog: list[dict[str, Any]]      # Role 4 rule_catalog(): description, mandatory, ...
    outcome: Outcome
    # Outcome.litigation_score is a placeholder until a scoring policy is approved (contract 7.1).
    litigation_score_status: Literal["not_computed"] = "not_computed"


@app.get("/cases/{case_id}/verification", response_model=VerificationOut)
def get_verification(case_id: str) -> VerificationOut:
    _get_case(case_id)
    if case_id not in VERIFICATIONS:
        raise HTTPException(
            409, f"Verification has not run for case {case_id}; call POST /cases/{case_id}/run first")
    v = VERIFICATIONS[case_id]
    report = verification_report(v)
    return VerificationOut(
        case_id=case_id,
        status=report["status"],
        stages=v.stages,
        errors=v.errors,
        doubles=list(v.doubles),
        tool_results=[ToolResultOut(**t.model_dump(), source=tool_source(t.raw_ref))
                      for t in v.tool_results],
        comparisons=report["comparisons"],
        findings=v.findings,
        not_checked=v.not_checked,
        rule_catalog=v.catalog,
        outcome=v.outcome,
    )


@app.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: str) -> Case:
    return _get_case(case_id)


@app.get("/cases/{case_id}/audit", response_model=list[AuditLine])
def get_audit(case_id: str) -> list[AuditLine]:
    _get_case(case_id)
    # Real version reads data/audit/<case_id>.jsonl, one AuditLine per line.
    path = FIXTURES / f"audit_{case_id}.json"
    if not path.exists():
        return []
    return [AuditLine.model_validate(x) for x in json.loads(path.read_text(encoding="utf-8"))]


@app.get("/documents/{doc_id}/pages/{n}")
def get_page(doc_id: str, n: int) -> Response:
    match = next(
        ((case.id, doc) for case in CASES.values() for doc in case.documents if doc.id == doc_id),
        None,
    )
    if match is None:
        raise HTTPException(404, f"Document {doc_id} not found")
    case_id, document = match
    path = UPLOADS / case_id / document.file
    if not path.exists():
        raise HTTPException(404, f"PDF content for document {doc_id} is not available")
    try:
        content = render_page_to_png(path, page_number=n)
    except (IndexError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Could not render PDF page: {exc}") from exc
    return Response(content=content, media_type="image/png")


class DecisionIn(BaseModel):
    action: Literal["confirm", "clear"]   # anything else -> 422 before our code runs
    reason_code: str
    user: str
    second_approver: str | None = None


@app.post("/findings/{finding_id}/decision", response_model=Decision, status_code=201)
def decide(finding_id: str, body: DecisionIn) -> Decision:
    finding = next((f for c in CASES.values() if c.outcome
                    for f in c.outcome.findings if f.id == finding_id), None)
    if finding is None:
        raise HTTPException(404, f"Finding {finding_id} not found")
    # Four-eyes rule from the plan: a red finding needs a second, different person.
    if finding.severity == "red" and (not body.second_approver or body.second_approver == body.user):
        raise HTTPException(422, "A red finding needs a second approver who is not the same user")
    d = Decision(finding_id=finding_id, action=body.action, reason_code=body.reason_code,
                 user=body.user, second_approver=body.second_approver,
                 at=datetime.now(timezone.utc))
    DECISIONS.append(d)
    return d


class LiveCheckIn(BaseModel):
    name: str | None = None
    cui: str | None = None


@app.post("/live-check")
def live_check(body: LiveCheckIn):
    raise HTTPException(501, "Live check lands in a later sprint (registry tools)")
