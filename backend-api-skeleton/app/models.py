"""
app/models.py — the contract from docs/CONTRACT.md, as Pydantic v2 models.

Why Pydantic and not plain dicts:
  * FastAPI uses these models to validate every request and response, so if
    someone's module returns a wrong shape, the API fails loudly in a test,
    not silently on stage.
  * The same models give the JSON schema we pass to complete(prompt, schema),
    so the LLM is forced into exactly the shape the rest of the code expects.
  * Java comparison: think of each class as a record/DTO with Bean Validation
    annotations; Literal[...] plays the role of an enum.

Only the lead changes this file. Others import from it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field as PField


class _Strict(BaseModel):
    # extra="forbid": an unknown key is an error, so a typo like "statuss"
    # is caught in tests instead of being silently dropped.
    model_config = ConfigDict(extra="forbid")


# ---------- shared enums (Literal = closed set of allowed strings) ----------
DocType = Literal["application", "bilant", "caf", "onrc", "ubo", "unknown"]
CaseStatus = Literal["new", "running", "green", "exceptions", "escalated", "decided"]
ToolStatus = Literal["ok", "not_found", "unavailable"]
Severity = Literal["red", "amber", "info"]
RuleResult = Literal["pass", "fail", "unknown"]
CheckerVerdict = Literal["agree", "disagree", "n/a"]
OutcomeResult = Literal["green", "exceptions", "escalated"]
Actor = Literal["maker", "checker", "tool", "rule", "human"]


class Document(_Strict):
    id: str
    type: DocType
    file: str                      # file name as uploaded
    pages: int = PField(ge=0)
    readable: bool = True          # False = no text layer (scanned) -> R14


class Field(_Strict):
    """One extracted value. It only exists if its quote was found on the page."""
    id: str
    name: str                      # e.g. "turnover", "cui", "directors"
    value: Any                     # number, string or list (directors, shareholders)
    doc_id: str
    page: int = PField(ge=1)       # 1-based, like a human reads it
    quote: str                     # exact text from the page
    verified: bool = True          # set by CODE after checking the quote, never by the model


class ToolResult(_Strict):
    id: str
    tool: str                      # anaf_company, anaf_financials, sanctions_screen, court_cases, ubo_register
    args: dict[str, Any]
    status: ToolStatus
    data: Optional[dict[str, Any]] = None   # parsed answer; None when unavailable
    raw_ref: Optional[str] = None           # path to the saved raw response (replayable)
    fetched_at: datetime


class Finding(_Strict):
    id: str
    rule_id: str = PField(pattern=r"^R(0[1-9]|1[0-5])$")   # R01..R15 only
    severity: Severity
    result: RuleResult
    evidence: list[str]            # "field:<id>" or "tool:<id>"
    explanation: str
    checker: CheckerVerdict = "n/a"


class Deduction(_Strict):
    """One line of the litigation score: every point lost links to a case number."""
    case_number: str
    category: str                  # insolvency | enforcement | anaf_plaintiff | commercial
    points: int                    # negative


class Outcome(_Strict):
    case_id: str
    result: OutcomeResult
    litigation_score: int = PField(ge=0, le=100)
    deductions: list[Deduction] = []   # proposed addition: the UI shows them (P5, screen 2)
    findings: list[Finding]


class Case(_Strict):
    id: str
    company_name: str
    cui: str
    status: CaseStatus
    documents: list[Document] = []
    # GET /cases/{id} returns these too (see the API table in the contract)
    fields: list[Field] = []
    tool_results: list[ToolResult] = []
    outcome: Optional[Outcome] = None


class Decision(_Strict):
    finding_id: str
    action: Literal["confirm", "clear"]
    reason_code: str
    user: str
    second_approver: Optional[str] = None   # required for red findings: enforced in the endpoint
    at: datetime


class AuditLine(_Strict):
    ts: datetime
    case_id: str
    step: str                      # e.g. "intake.extract", "maker.call", "rule.R03"
    actor: Actor
    input_ref: Optional[str] = None
    output_ref: Optional[str] = None
    model: Optional[str] = None    # filled for maker/checker steps
    prompt_version: Optional[str] = None


class CaseSummary(_Strict):
    """One row of GET /cases (the queue)."""
    id: str
    company_name: str
    status: CaseStatus
    red: int = 0
    amber: int = 0
