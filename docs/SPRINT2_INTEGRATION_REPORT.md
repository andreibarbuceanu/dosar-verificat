# Sprint 2 Integration Report

## Status

- Integration branch: `integration/sprint-2`
- Result: **integrated, with QA/evaluation role still missing**
- Remote push / pull request: **not performed**
- Test result: **466 passed, 1 skipped, 0 failed** (`pytest -q`)
- Runtime dependencies: real `app.tools`, `app.verification`, and `app.rules`; no test doubles

## Branches integrated

The implementation branches were merged in dependency order:

1. `origin/feat/s2-registry-data`
2. `origin/feat/s2-registry-tools`
3. `origin/feat/s2-verification`
4. `origin/feat/s2-rules`
5. `origin/feat/s2-integration`

`origin/feat/s2-evaluation` is an ancestor of this branch only because it still points to the
shared Sprint 2 base commit. It contains no Role 6 evaluation implementation or additional tests.
Minimal cross-role smoke coverage was therefore added in
`tests/integration/test_sprint2_runtime.py`, but this does not replace the missing independent QA role.

## Integration fixes

### Registry fixture compatibility

The financial registry fixture stores annual entries as a JSON list, while the Registry Tools
normalizer originally accepted only a single object. The normalizer now selects exactly one row
for the requested year, treats a missing year conservatively, and rejects duplicate-year rows.
The built-in-fallback test was isolated from the disk fixtures so it tests its intended path.

### Runtime wiring

The Role 5 wiring still selected `UnavailableRegistryTools` and `NoComparisons` after Roles 2 and 3
were merged. It now discovers and uses the real modules, retaining conservative doubles only when
a dependency is genuinely unavailable.

Role 3 returns a flat standalone comparison object, while the shared rules contract consumes
`left` and `right` value/evidence objects. A narrow adapter in `app/validation/wiring.py` converts
R03 turnover and R04 net-profit comparisons to the shared structure. It preserves source values,
uses resolvable field/tool evidence references, and reports an absolute numerical difference.

### Stale pre-integration assertions

Tests that intentionally expected `validation.status == "not_available"` while the runtime used
doubles were updated to require the fully integrated result. Separate wiring tests continue to
exercise the conservative fallback behavior for missing modules.

## End-to-end flow

The integrated runtime executes:

1. PDF ingestion, deterministic classification, and verified extraction.
2. CUI and fiscal-year selection from verified fields.
3. Simulated ANAF, financial, ONRC, and court registry queries.
4. Cross-document annual financial comparisons.
5. R01-R15 rules evaluation according to the Role 4 catalog.
6. Evidence validation and deterministic outcome calculation.
7. Exposure through the existing case, pipeline, and verification API responses.

The registry responses are simulated fixtures, not official live checks. The runtime does not read
`expected`, `planted_errors`, or ground-truth files to discover discrepancies.

## DEMO-02 acceptance result

The real PDFs under `pdfs/DEMO-02` were processed with the replay backend.

- PDF turnover for 2024: `12,400,000 RON`
- Simulated registry turnover for 2024: `8,100,000 RON`
- R03 comparison: `mismatch`
- Absolute difference: `4,300,000 RON`
- PDF evidence: `field:document_3-f11`
- Registry evidence: `tool:tool-demo02-financials`
- R03 Finding: `fail`, severity `red`
- Final outcome: `exceptions`
- Validation status: `completed`, with no doubles and no stage errors

The report brief and shared contract mention CUI `41738203`, but the committed DEMO-02 PDFs and
registry fixtures consistently contain `41738200`. The latter has a valid Romanian CUI check digit;
`41738203` does not. Integration preserves the source PDF/fixture data and records this discrepancy
instead of silently rewriting canonical inputs.

Other notable DEMO-02 results include R04 net profit `pass`, R13 court-case alert `fail`, and R14
document completeness `fail`. R02, R10, and R11 remain conservative `unknown` because the current
cross-document adapter does not emit those optional comparisons.

## Verification commands

Run the complete test suite:

```bash
cd ~/Desktop/dosar-verificat
pytest -q
```

Run only the integrated Sprint 2 smoke test:

```bash
cd ~/Desktop/dosar-verificat
pytest -q tests/integration/test_sprint2_runtime.py
```

Run DEMO-02 and print the complete pipeline result:

```bash
cd ~/Desktop/dosar-verificat
LLM_BACKEND=replay python scripts/run_demo_02.py
```

## Remaining limitations

- Role 6 (`feat/s2-evaluation`) has not delivered its evaluation harness, independent acceptance
  suite, or QA report.
- Registry data is simulated and must not be presented as a live ANAF, ONRC, or court response.
- R02, R10, and R11 have rule implementations but no integrated Role 3 comparison adapter yet, so
  they correctly return `unknown` rather than inventing matches.
- The litigation score remains the current Role 5 placeholder behavior; R13 still produces an
  evidence-backed finding and the final exception outcome.
- One existing environment-dependent test is skipped; all collected runnable tests pass.
