# Sprint 2 Backend Final Report

## Readiness summary

The Sprint 2 backend is integrated end to end on `integration/sprint2-finalization`. Registry
fixtures/tools, cross-document verification, the deterministic rules engine, outcome handling,
and the FastAPI views all execute in the normal upload pipeline. DEMO-02 detects the deliberately
inflated turnover as R03 `fail` and returns `exceptions`.

The backend is ready to begin Sprint 3 with known limitations: the independent Role 6 evaluation
harness was never delivered, R02/R10/R11 lack integrated comparison producers, and R12/R15 are
explicitly deferred. Registry results are synthetic fixtures and are never represented as live
official checks.

## Audit and integration status

Latest Sprint 2 integration branch audited: `integration/sprint-2` at `b0740b2`.

All remote feature tips are ancestors of that integration line:

- `feat/s2-registry-data`
- `feat/s2-registry-tools`
- `feat/s2-verification`
- `feat/s2-rules`
- `feat/s2-integration`
- `feat/s2-evaluation` (still points at the shared base; it contains no evaluation implementation)

No missing feature commits or duplicate competing implementations were found. The earlier
integration work already fixed the financial-fixture list format, real runtime wiring, and the
verification-to-rules comparison adapter. The complete suite was green before finalization.

## Components integrated

- Synthetic registry data for ANAF company/financials, ONRC, and court cases, separated under
  `fixtures/registry/` and labelled `source_mode=simulated_fixture`.
- Registry tools with normalized CUI lookup and conservative `not_found`/`unavailable` results.
- Verified-field comparisons for turnover and net profit, with resolvable field/tool evidence.
- Rules R01-R15 catalog and deterministic findings; deferred checks return `unknown`, never pass.
- FastAPI upload, run, pipeline, case, verification, page-rendering, and decision endpoints.
- Replay-mode E2E coverage using the committed DEMO-02 PDFs without runtime access to
  `expected`, `planted_errors`, or other ground truth.

## Bugs found and fixed

The classifier omitted `ubo` even though it is part of the public `Document.type` contract.
Consequently DEMO-02's beneficial-owner declaration was classified as `unknown`, and R14 falsely
reported the UBO document missing. Added the contract type, deterministic UBO indicators and
reason, a replay recording for the correctly typed prompt, and regression assertions. DEMO-02 now
classifies as `ubo, application, bilant, caf, onrc`; R14 passes.

The task brief and Sprint 2 contract example use CUI `41738203`, while the committed DEMO-02 PDFs
and registry fixtures consistently use `41738200`. The committed value has a valid Romanian CUI
check digit; `41738203` does not. Runtime preserves the PDF/fixture source value and does not
rewrite evidence to match narrative ground truth.

## DEMO-02 expected versus actual

| Check | Expected | Actual |
|---|---:|---:|
| PDF turnover (2024, RON) | 12,400,000 | 12,400,000 |
| Simulated ANAF turnover | 8,100,000 | 8,100,000 |
| Difference | 4,300,000 | 4,300,000 |
| R03 | `fail` | `fail` (red, field + tool evidence) |
| R13 | supported when evidence exists | `fail` (amber; simulated open enforcement) |
| R14 | all five required documents | `pass` |
| Final outcome | exceptions | `exceptions` |

The live HTTP response reported verification `completed`, no stage errors, no doubles, and all
four registry tool sources as `fixture`.

## Rules status

- Operational with direct/integrated evidence: R01, R03, R04, R05, R06, R07, R08, R09, R13,
  R14.
- Rule implementation exists but the integrated verifier does not yet emit its comparison: R02,
  R10, R11. These correctly return `unknown`.
- Deferred with no approved evidence source/model flag: R12 and R15. These correctly return
  `unknown` and appear in `not_checked`.

## Tests executed

- `python -m pytest -q`: complete automated suite; all runnable tests passed, one
  environment-dependent test skipped.
- Focused classifier/pipeline/API/integration tests: all passed.
- `LLM_BACKEND=replay python scripts/run_demo_02.py`: passed; R03 mismatch and R13 alert observed.
- Real FastAPI process on localhost with multipart `POST /cases`, `POST /cases/{id}/run`, and
  `GET /cases/{id}/verification`: HTTP 201, 200, and 200 respectively.

Replay mode is required for deterministic local E2E testing when no external AI service is
configured. No external AI service was used in this verification.

## API endpoints

- `GET /health`, `GET /cases`, `POST /cases`
- `GET /cases/{id}`, `POST /cases/{id}/run`
- `GET /cases/{id}/pipeline`, `GET /cases/{id}/verification`
- `GET /cases/{id}/audit`
- `GET /documents/{doc_id}/pages/{n}`
- `POST /findings/{finding_id}/decision`

## Remaining limitations

- Role 6 independent evaluation fixtures/harness and acceptance report remain missing.
- R02, R10, and R11 need comparison producers before they can produce pass/fail findings.
- R12 sanctions screening and R15 injection-to-rules integration are deferred by the contract.
- Registry checks are offline simulated fixtures, not official ANAF/ONRC/court responses.
- `Outcome.litigation_score` remains a placeholder; the verification API labels it
  `not_computed`.
- Storage and case state are local/in-memory, appropriate for the hackathon but not production.

## Run instructions

```bash
python -m pip install -r requirements.txt
python -m pytest -q
LLM_BACKEND=replay python scripts/run_demo_02.py
LLM_BACKEND=replay python -m uvicorn app.api.main:app --reload
```

Use the generated OpenAPI UI at `http://127.0.0.1:8000/docs` for manual backend-only requests.
