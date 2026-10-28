"""
app/api/main.py — the HTTP API from docs/CONTRACT.md.

Sprint 1 state: STUBS. The endpoints have their final paths and shapes, but
they serve the JSON in fixtures/api/ instead of running the pipeline. That lets
the frontend switch from reading files to calling the API today. As intake
lands, we replace the body of each endpoint; the path and shape stay the same,
so the frontend never notices.

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
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.models import AuditLine, Case, CaseSummary, Decision, Document

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "api"
UPLOADS = ROOT / "data" / "cases"

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
    # Stub: P3/P4 will report which registries answer right now.
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
    case_id = f"C-{uuid.uuid4().hex[:8]}"
    folder = UPLOADS / case_id
    folder.mkdir(parents=True, exist_ok=True)

    docs = []
    for i, f in enumerate(files, start=1):
        if not (f.filename or "").lower().endswith(".pdf"):
            raise HTTPException(400, f"{f.filename}: only PDF files are accepted")
        (folder / f.filename).write_bytes(await f.read())
        # type/pages are placeholders until PDF Processing and Classification run.
        docs.append(Document(id=f"{case_id}-d{i}", type="unknown", file=f.filename, pages=0))

    case = Case(id=case_id, company_name="", cui="", status="new", documents=docs)
    CASES[case_id] = case
    return case


@app.post("/cases/{case_id}/run", response_model=Case)
def run_case(case_id: str) -> Case:
    case = _get_case(case_id)
    # Stub: fixture cases already have their outcome. Real pipeline call goes here:
    #   from app.pipeline import run_intake
    #   case = run_intake(case)
    if case.outcome is None:
        case.status = "running"
    return case


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
def get_page(doc_id: str, n: int):
    # Stub: will render page n of the PDF to PNG with PyMuPDF for the evidence view.
    raise HTTPException(501, "Page rendering lands with PDF Processing")


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
