# Dosar Verificat — Sprint 2 Integration Contract

**Version:** 1.0 (proposed team baseline)  
**Target path:** `docs/SPRINT2_CONTRACT.md`  
**Baseline:** Sprint 1 integration (`app/models.py`, `docs/CONTRACT.md`, `app/pipeline.py`)  
**Scope:** registry fixtures, registry tools, cross-document verification, rules, outcomes, evaluation. **Frontend excluded.**

> **Authority:** This contract fixes the **Sprint 2 interoperability decisions**. The source of truth for existing public Pydantic models remains `app/models.py`. Do not silently change that file; any intentional model/API change needs team approval. The Sprint 1 archive was used to confirm existing names and constraints. Sprint 2 branch code created after that archive is not included in this review; adapt those implementations to this contract with the smallest possible compatible change.

## 0. Principles all six roles MUST follow

1. Runtime is allowed to consume **uploaded PDF bytes, extracted/verified fields and simulated registry tool responses**. It must **never** consume `companies.json`, `expected/`, `planted_errors`, or `eval/ground_truth/` to determine a result.
2. **Fixtures are not live official checks.** Label registry responses `simulated` in the UI/explanation and keep a traceable `raw_ref`.
3. Unknown/unavailable/ambiguous is **not** PASS. Never manufacture proof, registry values, legal policies, or findings.
4. Every runtime `Finding.evidence` reference resolves to a real `Field.id` (`field:<id>`) or `ToolResult.id` (`tool:<id>`) in the current case. No arbitrary refs such as `field:doc2-f3` unless that ID actually exists.
5. Money comparisons require matching **fiscal year and currency/unit**; do not compare unlike values. Use exact decimal arithmetic, not floating-point for money.
6. No automatic credit approval or rejection. Outcomes are internal review states only.
7. Changes to `docs/CONTRACT.md`, `app/models.py`, canonical fixtures, and public API shape are coordinator-owned. Everyone else works in their folder and raises a contract issue.
8. Checks are deterministic and reproducible. Evaluate dates relative to `credit_request.date` where relevant, not system `now()`. Actual fetch timestamps may reflect when a tool call ran.
9. Components must be usable independently via test doubles, because everyone works in parallel.
10. Do not commit or merge to `main` directly; create PRs toward the agreed integration branch.

## 1. Ownership and branch boundaries

| Role | Branch | Owns |
|---|---|---|
| 1 Registry Data | `feat/s2-registry-data` | `fixtures/registry/**`; test data for their own fixtures |
| 2 Registry Tools | `feat/s2-registry-tools` | `app/tools/**`; `tests/tools/**` |
| 3 Cross-Document Verification | `feat/s2-verification` | `app/verification/**`; `tests/verification/**` |
| 4 Rules Engine | `feat/s2-rules` | `app/rules/**`; `tests/rules/**` |
| 5 Integration & Outcome | `feat/s2-integration` | `app/validation/**`, `app/pipeline.py`, `app/api/**`; `tests/validation/**` |
| 6 QA & Evaluation | `feat/s2-evaluation` | `eval/**`, `tests/integration/**`, `tests/evaluation/**`, demo/evaluation scripts |

The frontend owner works separately on `feat/frontend`. No Sprint 2 member owns `web/`.

## 2. Existing public models — unchanged

Import from `app.models` (Pydantic v2, `extra="forbid"`):

- `Document`: `id`, `type` (`application|bilant|caf|onrc|ubo|unknown`), `file`, `pages`, `readable`.
- `Field`: `id`, `name`, `value`, `doc_id`, `page` (**1-based**), `quote` (**literal excerpt**), `verified` (**set by code**).
- `ToolResult`: `id`, `tool`, `args: dict`, `status` (`ok|not_found|unavailable`), `data: dict|null`, `raw_ref: str|null`, `fetched_at: datetime`.
- `Finding`: `id`, `rule_id` (`R01`–`R15`), `severity` (`red|amber|info`), `result` (`pass|fail|unknown`), `evidence: list[str]`, `explanation`, `checker` (`agree|disagree|n/a`).
- `Outcome`: `case_id`, `result` (`green|exceptions|escalated`), `litigation_score: int` (0–100), `deductions: list[Deduction]`, `findings: list[Finding]`.
- `Case`: `id`, `company_name`, `cui`, `status`, `documents`, `fields`, `tool_results`, `outcome`.

**No new keys** may be injected into these serialized models unless the owner updates `app/models.py` and its tests. `verified` is never set by an LLM.

## 3. Registry fixtures — Role 1 → Role 2

### 3.1 Paths, manifest and data format

All registry files go in `fixtures/registry/<CASE_ID>/`:

```text
fixtures/registry/
  cases_manifest.json
  DEMO-02/
    anaf_company.json
    anaf_financials.json
    onrc.json
    court_cases.json
```

`cases_manifest.json` is an offline fixture index used by the *mock provider only*. Minimum shape:

```json
{
  "cases": {
    "DEMO-02": {
      "cui": "41738203",
      "paths": {
        "anaf_company": "DEMO-02/anaf_company.json",
        "anaf_financials": "DEMO-02/anaf_financials.json",
        "onrc_company": "DEMO-02/onrc.json",
        "court_cases": "DEMO-02/court_cases.json"
      }
    }
  }
}
```

For live-like behavior, registry tools must look up by normalized **CUI**, never by the `expected` outcome. The case ID is only an internal fixture lookup aid. No registry fixture contains `expected` or `planted_errors`.

### 3.2 Canonical response payloads (inside ToolResult.data)

`anaf_company`:

```json
{
  "cui": "41738203",
  "active": true,
  "vat_registered": true,
  "vat_since": "2019-10-01",
  "e_factura": true
}
```

`anaf_financials`:

```json
{
  "cui": "41738203",
  "year": 2024,
  "currency": "RON",
  "turnover": 8100000,
  "total_revenue": 8240000,
  "total_expenses": 7690000,
  "net_profit": 462000
}
```

`onrc_company`:

```json
{
  "cui": "41738203",
  "name": "AGRO NORD TRANS SRL",
  "reg_com": "J12/1834/2019",
  "status": "funcțiune",
  "directors": [{"name": "Andrei Mureșan", "can_sign": true}]
}
```

`court_cases`:

```json
{
  "cui": "41738203",
  "cases": [
    {
      "number": "2318/117/2025",
      "subject": "executare silită",
      "category": "enforcement",
      "party_role": "debitor",
      "status": "open",
      "registered": "2025-05-12"
    }
  ]
}
```

These are **synthetic values from DEMO-02**, not claims about an actual company. Other optional fields may exist inside `ToolResult.data`; the keys shown are the minimal shared fields. Keep `year` and `currency` explicit for financials.

## 4. Registry tools — Role 2 interface

```python
from app.models import ToolResult

def get_anaf_company(cui: str) -> ToolResult: ...
def get_anaf_financials(cui: str, year: int) -> ToolResult: ...
def get_onrc_company(cui: str) -> ToolResult: ...
def get_court_cases(cui: str) -> ToolResult: ...
```

The tool layer has no knowledge of PDF content, rule IDs, or case outcomes.

**Result rules:**

- `status="ok"`: `data` contains the matched canonical response.
- `status="not_found"`: a completed lookup did not find a matching record; `data=None`. Do not conclude the company is nonexistent without verified coverage.
- `status="unavailable"`: fixture or provider cannot be queried reliably; `data=None`.
- `tool` is exactly `anaf_company`, `anaf_financials`, `onrc_company`, or `court_cases`.
- `args` mirrors normalized lookup arguments, e.g. `{"cui":"41738203","year":2024}`.
- `raw_ref` identifies the fixture used; no fake official URL.
- `fetched_at` is timezone-aware.
- Assign unique `ToolResult.id` per case/run/tool/arguments, or reuse stable IDs for identical replay calls. References must remain stable within one result.
- No `status="error"` or `status="missing"`; these are not valid enum values.

Example, valid against Sprint 1 `ToolResult`:

```json
{
  "id": "t-demo02-anaf-financials-2024",
  "tool": "anaf_financials",
  "args": {"cui": "41738203", "year": 2024},
  "status": "ok",
  "data": {
    "cui": "41738203",
    "year": 2024,
    "currency": "RON",
    "turnover": 8100000
  },
  "raw_ref": "fixtures/registry/DEMO-02/anaf_financials.json",
  "fetched_at": "2026-10-20T00:00:00+00:00"
}
```

The timestamp shown is an **example fixture timestamp**, not evidence of a live lookup.

## 5. Verification comparison — Role 3 → Role 4

This is a **new internal DTO**, not a replacement for `Finding` and not a change to `app/models.py`. Implement it in `app/verification/` using typed Python models.

### 5.1 Canonical JSON representation

```json
{
  "check_id": "turnover:2024:41738203",
  "rule_id": "R03",
  "status": "mismatch",
  "left": {
    "value": 12400000,
    "evidence": "field:actual_field_id"
  },
  "right": {
    "value": 8100000,
    "evidence": "tool:actual_tool_result_id"
  },
  "difference": 4300000,
  "explanation": "Cifra de afaceri pentru 2024 diferă între bilanț și registrul financiar simulat."
}
```

Schema:

| Property | Type | Rule |
|---|---|---|
| `check_id` | `str` | Stable unique check identifier within a case |
| `rule_id` | `"R03" \| null` | R03 for turnover vs registry; null for comparisons not yet mapped to an agreed rule |
| `status` | `"match" \| "mismatch" \| "unknown"` | Never return match without sufficient evidence |
| `left`, `right` | `{value: JSON value, evidence: str|null}` | Evidence refs resolve against current `Case` |
| `difference` | `number \| null` | Absolute numeric difference only when same currency/year and both numeric |
| `explanation` | `str` | Short explanation, identify sources and uncertainty |

For internal Python use, `Decimal` is recommended; serialize safely to JSON at the API boundary. `difference` may be an integer for whole RON values. For `unknown`, `difference=null`, and missing side value/evidence may be null.

### 5.2 Comparison input boundary

Public entry points may vary by implementation; their **semantics and output** must agree:

```python
# Suggested adapter signatures (not mandatory if existing Role 3 API already works):
compare_turnover(
    pdf_field: Field,
    registry_result: ToolResult,
    *,
    fiscal_year: int,
    currency: str = "RON",
) -> ComparisonResult

compare_fields(
    left_field: Field,
    right_field: Field,
    *,
    check_id: str,
    rule_id: str | None = None,
) -> ComparisonResult
```

**Do not change a working Role 3 public API just to match these function names.** The integrator may wrap it. Role 3 must document its actual exports in `app/verification/README.md`.

### 5.3 Comparison logic

- CUI: strip optional `RO` prefix/whitespace, retain significant digits, never compare by integer if zero preservation matters.
- Names: Unicode normalization, Romanian diacritic folding, whitespace/case normalization. A fuzzy match alone must not become a conclusive identity PASS.
- Money: compare as Decimal; require same fiscal year and currency. Do not compare turnover to `total_revenue`.
- Administrator/signatory: require names and signatory authority evidence, do not infer authority from name match alone.
- Only `Field.verified=True` may be used as positive evidence. A verified field still might be factually false, so comparison is required.
- If tool status is unavailable/not_found, required inputs are absent, evidence cannot be resolved, or fiscal year differs: `unknown`.
- With matching reliable values: `match`; with confirmed different values: `mismatch`.
- Do not attempt to fetch registries or evaluate rules inside comparison functions.

## 6. Rules engine — Role 4 → Role 5

Rules are deterministic and consume **ComparisonResult + ToolResult + Field + Document** as appropriate, without ground-truth answers.

**Only two IDs have currently supported scenario meaning:**

| Rule | Agreed check | Failure condition | Missing/unclear evidence |
|---|---|---|---|
| `R03` | Financial turnover mismatch | Same-year, same-currency verified PDF turnover differs from simulated registry turnover | `unknown` |
| `R13` | Synthetic open enforcement/litigation alert | **Provisional scenario mapping:** identified open case with reliable company match. Exact policy must be approved before treating it as bank policy | `unknown` |

**Identity/CUI comparisons:** performed by Role 3, but leave `rule_id=null` unless the team supplies the approved mapping from existing R01–R15 definitions. Do not silently assign R01 or R02.

**Remaining R01–R15:** reserved IDs; their meaning is **not defined in the reviewed Sprint 1 `docs/CONTRACT.md`**. The Rule Owner must obtain the official definitions before implementing them. They are **not automatically pass**.

### 6.1 Finding mapping

Use exactly `app.models.Finding`.

- A confirmed comparison `R03` `mismatch` produces a `Finding` with `rule_id="R03"`, `result="fail"`, `severity="red"` (Sprint 2 demo policy) and BOTH valid evidence refs.
- A confirmed comparison `R03` `match` may produce `pass` if both sources were available and comparable; do not report unsupported checks as pass.
- A comparison `R03` `unknown` produces `unknown` and an informative explanation; severity `amber` or `info` as documented by Rule Owner.
- R13 may report the synthetic court record using its `tool:<id>` evidence, while clearly labelling the finding as a **scenario alert**, not a confirmed judicial risk score.
- `checker="n/a"` in Sprint 2 (Maker/Checker is later).
- `Finding.id` is stable and unique per case/rule/relevant subject, e.g. `finding:DEMO-02:R03:2024`.
- `evidence` contains only references to actual IDs in the active `Case`.
- Pass findings and unknown findings may be included, but **never fabricate a finding for an unimplemented check**.

### 6.2 All other rules

Until the authoritative mapping is published, a rule catalog may state `implemented: false`, but runtime should not emit a fabricated `pass` for it. `expected.all_other_rules="pass"` is an evaluation fixture expectation **not** a license to mark unimplemented rules as passing.

## 7. Outcome orchestration — Role 5

`Case.outcome` uses existing `Outcome` and `Case.status` enum values.

Required decision policy for implemented, mandatory checks:

1. If **any verified fail finding** exists → `Outcome.result="exceptions"` and `Case.status="exceptions"`.
2. Else if a required check is `unknown`, critical evidence is missing, or registry provider is unavailable → `Outcome.result="escalated"` and `Case.status="escalated"`.
3. Else if every **configured mandatory check** has been executed and passed, with complete required evidence → `Outcome.result="green"` and `Case.status="green"`.
4. If there are zero configured/executed mandatory checks, **never** return green.

`Outcome.findings` includes evaluated findings. Do not confuse a rule `pass` with final approval of financing.

### 7.1 Litigation score limitation

Existing `Outcome` **requires** `litigation_score` (0–100) and supports `deductions`; no canonical deduction formula is present in the reviewed Sprint 1 contract.

For Sprint 2, the integrator must either:

- Obtain and implement an **approved, documented scoring policy**, or
- Use an explicitly documented **non-evaluated placeholder** compatible with the Pydantic model, e.g. `litigation_score=100`, `deductions=[]`, while treating this number as **not computed / not available** and never displaying it as a genuine assessed score.

Because the current model cannot represent `null` for this field, do **not** infer that 100 means “no litigation risk.” A future schema revision should add explicit score status; only the coordinator may make that breaking contract change.

### 7.2 API compatibility

Preserve the existing endpoints from `docs/CONTRACT.md`, especially:

- `POST /cases` — multipart PDFs.
- `POST /cases/{id}/run` — run processing and verification.
- `GET /cases/{id}` — `Case` with `documents`, `fields`, `tool_results`, `outcome`.
- `GET /cases/{id}/pipeline` — stage details; return actual validation status after integration.
- `GET /cases` — list status and red/amber counts.

No invented API response keys in `Case` without a coordinated model change. Keep evidence references resolvable by the frontend.

## 8. Evaluation — Role 6

Evaluation may read `expected`, `planted_errors`, and `eval/ground_truth`; runtime must not. Tests must assert:

- DEMO-02: extracted 2024 PDF turnover `12_400_000` stays intact; registry return `8_100_000`; `difference=4_300_000`; `R03=fail`; `Outcome.result=exceptions`.
- Evidence IDs resolve to a real `Field` and `ToolResult`.
- Correct fiscal year/currency are checked before numeric comparison.
- Clean verified match → match/R03 pass (with no other unresolved mandatory checks for green).
- Missing registry value → unknown; not green.
- Wrong CUI or wrong fiscal year → not a valid match.
- Empty/illegible PDF → no fabricated field proof.
- Runtime does not import/open ground-truth files.
- Sprint 1 tests still pass.
- All reports distinguish fixture-only evaluation from external registry validation.

## 9. Integration acceptance checklist

- [ ] Sprint 2 base contains this contract at `docs/SPRINT2_CONTRACT.md`.
- [ ] Role 1 fixture paths and canonical keys match Section 3.
- [ ] Role 2 returns valid Sprint 1 `ToolResult` models.
- [ ] Role 3 comparison JSON semantics match Section 5.
- [ ] Role 4 maps `R03` and supported scenario `R13` to valid `Finding` objects.
- [ ] Role 5 wires modules into the existing pipeline/API without breaking Sprint 1.
- [ ] Role 6 tests DEMO-02, clean case, incomplete case and leak prevention.
- [ ] Full `python3 -m pytest -v` suite passes on the integration branch.
- [ ] `DEMO-02` yields a real runtime R03 exception (not read from `expected`).
- [ ] Frontend integration receives compatible `Case` JSON without a schema rewrite.

## 10. Publishing and branch synchronization

**Recommended sequence:** the coordinator adds this document to `sprint2/base` and pushes it. The already-created feature branches then pull the contract from `sprint2/base`, without rewriting their published history.

From a clean working tree:

```bash
git fetch origin
git switch sprint2/base
# Place this file at docs/SPRINT2_CONTRACT.md
git add docs/SPRINT2_CONTRACT.md
git commit -m "docs: establish Sprint 2 integration contract"
git push origin sprint2/base
```

On a feature branch **after** local changes are committed or safely stashed:

```bash
git fetch origin
git switch feat/s2-verification   # replace with teammate's branch
git merge origin/sprint2/base
```

If files conflict, stop, inspect and resolve; do not blindly overwrite working code. Team members should verify their module still passes tests and adapt any discrepant contract fields. Merge the six features into a **new Sprint 2 integration branch** and test before touching `main`.

---

### Provenance and unresolved decisions

- **Grounded in Sprint 1 archive:** exact Pydantic model fields/enums, strict extra-field rejection, PDF pipeline, API paths, evidence semantics, ground-truth isolation.
- **Sprint 2 conventions fixed here:** registry fixture layout, `ComparisonResult` representation, cross-module boundaries, matching/outcome priority, test requirements.
- **Not established by the reviewed Sprint 1 source:** full R01–R15 meanings, official R13 risk policy, litigation score deductions. These are explicitly left for team approval rather than invented.
