# Contract

The shapes every module codes against. **Only the lead changes this file and
`app/models.py`.** Need a change? Ask the lead; never change a shape alone.
The source of truth in code is `app/models.py` (Pydantic); this page explains it.

## Data shapes

| Model | Fields |
|---|---|
| Case | id, company_name, cui, status (`new·running·green·exceptions·escalated·decided`), documents, fields, tool_results, outcome |
| Document | id, type (`application·bilant·caf·onrc·ubo·unknown`), file, pages, readable |
| Field | id, name, value, doc_id, page (1-based), quote (exact text), verified (set by code) |
| ToolResult | id, tool, args, status (`ok·not_found·unavailable`), data, raw_ref, fetched_at |
| Finding | id, rule_id (`R01`–`R15`), severity (`red·amber·info`), result (`pass·fail·unknown`), evidence (`field:<id>` / `tool:<id>`), explanation, checker (`agree·disagree·n/a`) |
| Outcome | case_id, result (`green·exceptions·escalated`), litigation_score (0–100), deductions, findings |
| Deduction | case_number, category, points |
| Decision | finding_id, action (`confirm·clear`), reason_code, user, second_approver, at |
| AuditLine | ts, case_id, step, actor (`maker·checker·tool·rule·human`), input_ref, output_ref, model, prompt_version |

Additions to the team plan: `Outcome.deductions` (the UI shows them) and
`Case.fields` / `Case.tool_results` (returned by `GET /cases/{id}`).

## API

| Endpoint | What it does | Sprint 1 |
|---|---|---|
| `POST /cases` | Upload PDFs (multipart, field `files`); returns the Case | real |
| `POST /cases/{id}/run` | Start the pipeline | stub |
| `GET /cases` | Queue with status and red/amber counts | real |
| `GET /cases/{id}` | Case with Documents, Fields, ToolResults, Outcome | real |
| `GET /cases/{id}/audit` | Audit lines; UI polls every second | fixtures |
| `GET /documents/{id}/pages/{n}` | One PDF page as PNG | 501 |
| `POST /findings/{id}/decision` | Confirm/clear; red needs a different second approver | real |
| `POST /live-check` | `{name}` or `{cui}`: run tools live | 501 |
| `GET /health` | Which registries answer | stub |

## Model interface

`from app.llm import complete` → `complete(prompt, schema) -> dict`.
`LLM_BACKEND=replay` (default, recorded answers in `fixtures/llm/`), `cli`
(`claude -p`), `api` (`ANTHROPIC_API_KEY`). `LLM_RECORD=1` saves live answers
for replay. Nobody else imports `anthropic` or calls `claude`.

## Sprint 1: who owns what

| Branch | Owns | Exposes |
|---|---|---|
| feat/pdf-processing | `app/intake/pdf.py` | `extract_pages(path) -> list[Page]` (text per page, readable flag) |
| feat/ai-classification | `app/intake/classify.py` | `classify(pages: list[str]) -> DocType` |
| feat/ai-extraction | `app/intake/extract.py` | `extract(doc_type, pages) -> list[Field]` (quotes verified in code) |
| feat/backend-api (lead) | `app/models.py`, `app/llm/`, `app/pipeline/`, `app/api/`, `docs/`, `storage/` (runtime, not in git) | the API above |
| feat/frontend | `web/` | — |
| data & testing | `data/synthetic/`, `fixtures/registry/`, `eval/` | `companies.json`, demo PDFs |

Change files only in your own folder.

## Rules that protect the eval

- `companies.json`, `expected` and `planted_errors` are ground truth. The
  pipeline never reads them; it sees only PDFs and registry answers.
- Dates are relative to the credit request date, never `now()`, so results
  are reproducible.
