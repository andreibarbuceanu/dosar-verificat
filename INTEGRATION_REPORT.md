# Sprint 1 backend integration

## Included components

- Data fixtures and synthetic PDFs
- PDF processing and page rendering
- Deterministic Romanian document classification
- Evidence-verifying AI extraction
- FastAPI backend

The integrated flow is `PDF -> text pages -> classification -> extraction -> JSON/API`.
DEMO-02 uses the existing replay backend because an external model is not required for
the offline demo. Replay candidates are still checked by extraction code against exact
page quotes and values.

## Validation status

The data-validation branch provides `check_intake.py`, an offline evaluator for complete
result sets. It does not expose a runtime validator for one case. Therefore the pipeline
returns `validation.status = "not_available"` and no fabricated findings. In particular,
the PDF turnover of 12,400,000 RON is extracted and preserved, but the discrepancy against
the reference turnover is not reported as a runtime finding yet.

Neither `companies.json` nor its `expected` or `planted_errors` sections are read by the
pipeline.

## Run

```bash
python3 -m pip install -r requirements.txt
LLM_BACKEND=replay python3 scripts/run_demo_02.py
uvicorn app.api.main:app --reload
```

Frontend clients can upload PDFs with multipart field `files` to `POST /cases`, invoke
`POST /cases/{id}/run`, read the case with `GET /cases/{id}`, inspect stage details at
`GET /cases/{id}/pipeline`, and request PNG evidence pages from
`GET /documents/{document_id}/pages/{page_number}`.
