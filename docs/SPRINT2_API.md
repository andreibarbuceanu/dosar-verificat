# Sprint 2 API for the frontend

What changed in Sprint 2 and how to read it. The data shapes are still the
ones in `docs/CONTRACT.md` / `app/models.py`. **No existing endpoint or field
was removed or renamed**; Sprint 2 only fills in fields that were empty before
and adds one endpoint, `GET /cases/{id}/verification`.

Base URL in development: `http://localhost:8000` (interactive docs at `/docs`).

## Before you build on it

- **Registry data is simulated.** Every registry answer comes from a fixture
  file, not from a live official lookup. Show it as "simulated" in the UI
  (SPRINT2_CONTRACT §0.2). `tool_results[].source` tells you which.
- **Don't show the litigation score.** `outcome.litigation_score` is always
  `100` for now, because no scoring policy has been approved yet. It does
  **not** mean "no litigation risk". `GET /cases/{id}/verification` says so
  explicitly: `litigation_score_status: "not_computed"`.
- **Test doubles.** Until the registry and comparison modules (and, where it
  isn't merged yet, the rules module) are wired in, the backend runs on
  stand-ins that find nothing. Registries answer `unavailable`, so an uploaded
  case is never `green`, and `/verification` lists the stand-ins in `doubles`.
  When `doubles` is non-empty, show "verification not yet available".
- **Rules come from the rules engine's catalog (`rule_catalog`).** Each rule
  R01–R15 is either evaluated or **not checked this sprint** (currently R12
  sanctions and R15 injection). Not-checked rules are never a pass and never
  block green. They are left out of `outcome.findings` and listed in
  `not_checked` on `/verification`. Show them as "neverificat în acest sprint",
  separately from real `unknown` results.

## What the outcome means

`outcome.result`, and the case `status` after a run (they always match):

| Value | Meaning for the analyst | When |
|---|---|---|
| `green` | Every mandatory check ran on complete evidence and passed. This is **not** a credit approval. | No evaluated rule failed, every evaluated rule marked `mandatory` in the catalog passed, and every registry answered `ok` |
| `exceptions` | At least one check found a real discrepancy, backed by evidence. A person must review each failed finding. | Any evaluated finding with `result: "fail"`, mandatory or not |
| `escalated` | The system could not finish verifying, so a person has to. It never means "fine". | No fail, but something is missing: a mandatory rule came back `unknown` or produced no finding, a registry was unavailable or returned nothing, there was no CUI or fiscal year in the PDFs, or the verification stage errored |

The order matters: a fail always wins (`exceptions`), even when something else
is also missing. A case with zero executed mandatory checks is never `green`.
An `unknown` on an **optional** rule (for example R04 while its comparison
doesn't exist yet) is shown but does not block green. Which rules are mandatory
is decided in `app/rules/rules.yaml`, and the frontend reads it from
`rule_catalog` on `/verification`. Don't hard-code the list.

Case `status` values over a case's life: `new` (uploaded) → `green` /
`exceptions` / `escalated` (after `POST /run`). `running` only appears on
cases processed before Sprint 2.

## Endpoints

| Endpoint | Sprint 2 change |
|---|---|
| `GET /health` | none |
| `GET /cases` | none in shape. After a run, `status` is the outcome result |
| `POST /cases` | none |
| `POST /cases/{id}/run` | now also fills `tool_results`, `outcome` and the final `status` |
| `GET /cases/{id}` | same as `/run`: `tool_results` and `outcome` are filled |
| `GET /cases/{id}/verification` | **new**: stage details, errors, comparisons, tool source |
| `GET /cases/{id}/pipeline` | `validation` now reports the real status. Extra keys were added |
| `GET /cases/{id}/audit` | none (fixtures only) |
| `GET /documents/{id}/pages/{n}` | none |
| `POST /findings/{id}/decision` | none; works on Sprint 2 findings too |
| `POST /live-check` | still `501` |

The examples below come from DEMO-02 with simulated registry answers. Ids such
as `C-10c8cd36` are generated per upload.

### `GET /cases`: the queue

```json
[
  {"id": "C-10c8cd36", "company_name": "AGRO NORD TRANS SRL",
   "status": "exceptions", "red": 1, "amber": 0}
]
```

`red` and `amber` count **failed** findings by severity. Use `status` to colour
the row; after a run it equals `outcome.result`.

### `POST /cases`: upload

`multipart/form-data`, field `files` (one or more PDFs). Response `201`:

```json
{"id": "C-10c8cd36", "company_name": "", "cui": "", "status": "new",
 "documents": [{"id": "C-10c8cd36-d1", "type": "unknown", "file": "01_cerere.pdf",
                "pages": 0, "readable": true}],
 "fields": [], "tool_results": [], "outcome": null}
```

### `POST /cases/{id}/run` and `GET /cases/{id}`: the full case

Both return the same `Case`. The keys are unchanged from Sprint 1.

```json
{
  "id": "C-10c8cd36",
  "company_name": "AGRO NORD TRANS SRL",
  "cui": "41738200",
  "status": "exceptions",
  "documents": [{"id": "C-10c8cd36-d3", "type": "bilant", "file": "03_bilant.pdf",
                 "pages": 2, "readable": true}],
  "fields": [{"id": "C-10c8cd36-d3-f11", "name": "turnover", "value": 12400000,
              "doc_id": "C-10c8cd36-d3", "page": 2,
              "quote": "Cifra de afaceri netă ... 12.400.000", "verified": true}],
  "tool_results": [{
    "id": "t-anaf_financials-41738200-2024",
    "tool": "anaf_financials",
    "args": {"cui": "41738200", "year": 2024},
    "status": "ok",
    "data": {"cui": "41738200", "year": 2024, "currency": "RON", "turnover": 8100000},
    "raw_ref": "fixtures/registry/DEMO-02/anaf_financials.json",
    "fetched_at": "2026-10-20T00:00:00Z"
  }],
  "outcome": {
    "case_id": "C-10c8cd36",
    "result": "exceptions",
    "litigation_score": 100,
    "deductions": [],
    "findings": [{
      "id": "finding-R03-C-10c8cd36",
      "rule_id": "R03",
      "severity": "red",
      "result": "fail",
      "evidence": ["field:C-10c8cd36-d3-f11", "tool:t-anaf_financials-41738200-2024"],
      "explanation": "Cifra de afaceri pentru 2024 diferă între bilanț și registrul financiar simulat.",
      "checker": "n/a"
    }]
  }
}
```

The arrays are shortened here. A real case has every document and field, and
four tool results: `anaf_company`, `anaf_financials`, `onrc_company` and
`court_cases`.

**Resolving evidence.** Every entry in `finding.evidence` points into this same
case:
- `field:<id>` is in `fields[]`. Show `quote`, and open
  `GET /documents/{doc_id}/pages/{page}` to show the page.
- `tool:<id>` is in `tool_results[]`. Show `data` and label it simulated.
- `doc:<id>` is in `documents[]`. Only R14 (documents present and readable)
  uses it.

The backend rejects findings whose evidence doesn't resolve, so a missing id is
a backend bug. Please report it.

A rerun never duplicates results: `tool_results` and `outcome` are replaced
each time. `POST /run` on a case that already has an outcome returns it
unchanged.

### `GET /cases/{id}/verification`: Sprint 2 details (new)

Use it for the "how was this verified" panel. Everything in `GET /cases/{id}`
is still the complete source for the case itself.

```json
{
  "case_id": "C-10c8cd36",
  "status": "completed",
  "stages": {"inputs": "ok", "registries": "ok", "comparisons": "ok",
             "rules": "ok", "outcome": "ok"},
  "errors": [],
  "doubles": [],
  "tool_results": [{
    "id": "t-anaf_financials-41738200-2024", "tool": "anaf_financials",
    "args": {"cui": "41738200", "year": 2024}, "status": "ok",
    "data": {"cui": "41738200", "year": 2024, "currency": "RON", "turnover": 8100000},
    "raw_ref": "fixtures/registry/DEMO-02/anaf_financials.json",
    "fetched_at": "2026-10-20T00:00:00Z",
    "source": "fixture"
  }],
  "comparisons": [{
    "check_id": "turnover:2024", "rule_id": "R03", "status": "mismatch",
    "left":  {"value": 12400000, "evidence": "field:C-10c8cd36-d3-f11"},
    "right": {"value": 8100000,  "evidence": "tool:t-anaf_financials-41738200-2024"},
    "difference": 4300000,
    "explanation": "Cifra de afaceri: bilanț vs registru financiar simulat."
  }],
  "findings": ["… same objects as outcome.findings (evaluated rules only) …"],
  "not_checked": [{
    "id": "finding-R12-C-10c8cd36", "rule_id": "R12", "severity": "red",
    "result": "unknown", "evidence": [], "checker": "n/a",
    "explanation": "Neimplementat în Sprint 2: sursă de sancțiuni neintegrată."
  }],
  "rule_catalog": [{
    "rule_id": "R03",
    "description": "Cifra de afaceri din bilanț este egală cu cea depusă la ANAF (același CUI și an).",
    "severity": "red", "implemented": true, "mandatory": true,
    "inputs": ["comparison:R03", "tool:anaf_financials", "field:turnover", "field:fiscal_year"],
    "thresholds": {"tolerance_abs": {"value": 0, "source": "team doc rule catalogue", "confirmed": false}}
  }],
  "outcome": {"… same object as in GET /cases/{id} …": null},
  "litigation_score_status": "not_computed"
}
```

| Field | Values |
|---|---|
| `status` | `completed`; `completed_with_errors` (look at `errors`); `failed` (the stage crashed, so the case is escalated); `not_available` (running on test doubles, see `doubles`) |
| `stages.<name>` | `ok`, `error`, `skipped`. For example, `registries: "skipped"` means no CUI was found in the PDFs |
| `errors` | Readable messages (Romanian or technical), one per problem. Show them on escalated cases |
| `tool_results[].source` | `fixture` (simulated registry file), `unknown` (no file, e.g. an unavailable registry). `live` is reserved and not produced in Sprint 2 |
| `findings` | Evaluated rules only, exactly `outcome.findings` |
| `not_checked` | Rules the engine doesn't implement this sprint. `result` is always `unknown` and the explanation starts with `Neimplementat în Sprint 2:`. Label them "neverificat în acest sprint" |
| `rule_catalog` | One entry per rule R01–R15: `description` (Romanian, ready to display), `severity`, `implemented`, `mandatory`, `inputs`, `thresholds`. A threshold with `confirmed: false` is a working assumption, not bank policy |
| `comparisons` | Raw comparison detail, for display only. **Its exact shape may change** until the comparison module is merged, so build UI logic on `findings` and `evidence`, not on this |

The same response while the backend still runs on test doubles:

```json
{"status": "not_available",
 "doubles": ["registry_tools", "comparison_engine", "rules_engine"],
 "tool_results": [{"tool": "anaf_company", "status": "unavailable", "data": null,
                   "raw_ref": null, "source": "unknown", "…": "…"}],
 "findings": [], "outcome": {"result": "escalated", "…": "…"}, "…": "…"}
```

### `GET /cases/{id}/pipeline`: raw stage dump (debug)

Per-document classification and extraction details, unchanged. `validation`
keeps `status`, `findings` and `reason`, and now also has `result`, `stages`,
`errors`, `doubles`, `not_checked` (rule ids) and `comparisons`. The top level now also has `fields`,
`tool_results` and `outcome`. Prefer `/verification` in the UI.

### `POST /findings/{id}/decision`

Unchanged. Sprint 2 finding ids look like `finding-R03-C-10c8cd36`, one per
rule per case, and they stay stable across reruns. A `red` finding needs a
`second_approver` different from `user`.

## Errors

| Code | When | `detail` example |
|---|---|---|
| `404` | Unknown case, on any `/cases/{id}…` route | `Case NOPE not found` |
| `409` | `/verification` before the case was run. Seeded fixture cases (e.g. `DEMO-02`) also return this, because they were never verified at runtime | `Verification has not run for case C-1; call POST /cases/C-1/run first` |
| `404` | `/pipeline` before the case was run | `Pipeline has not run for case C-1` |
| `422` | `/run`: a PDF could not be processed | `One or more PDFs could not be processed: …` |
| `503` | `/run`: extraction (the model call) failed | `Extraction failed for …` |

A failure *inside* verification never produces an error code. The run returns
`200`, the case is `escalated`, and `/verification` shows `status: "failed"`
with the message in `errors`.
