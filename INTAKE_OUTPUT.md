# What each Sprint 1 role must output (so the Data role can test it)

One JSON file per role: a **list** with one entry per PDF in `pdfs/`. `file` is the path of the PDF (`pdfs/EVAL-04/document_6.pdf`; only the last two parts, `EVAL-04/document_6.pdf`, are used to match). Field names are exactly the ones in `expected/intake_truth.json`. The shapes follow the `Document` and `Field` models in `app/models.py` (see docs/CONTRACT.md on the integration branch).

## 1. PDF Processing: text per page

```json
[{"file": "pdfs/EVAL-04/document_1.pdf",
  "pages": [
    {"page": 1, "text": "BILANȚ ... NOVA PRINT MEDIA SRL ...", "readable": true},
    {"page": 2, "text": "", "readable": false}
  ]}]
```
- `readable` is false when the page has no text layer (a scanned image). Its `text` stays empty.
- Keep hidden text (white, tiny): it is in the text layer. The Extraction step flags it.
- Test: `python check_intake.py pdf results.json`

## 2. AI Classification: document type

```json
[{"file": "pdfs/EVAL-04/document_2.pdf", "doc_type": "unknown", "confidence": 0.93}]
```
- `doc_type` is one of `application`, `bilant`, `caf`, `onrc`, `ubo`, `unknown`. The invoice must be `unknown`.
- `confidence` is a number from 0 to 1.
- Test: `python check_intake.py classify results.json`

## 3. AI Extraction: fields with value, quote and page

```json
[{"file": "pdfs/EVAL-04/document_6.pdf",
  "fields": {
    "caf_number":    {"value": "CAF-...", "quote": "CAF-...", "page": 1},
    "caf_issue_date": {"value": "2026-10-09", "quote": "09.10.2026", "page": 1},
    "caf_debts_total": {"value": 0, "quote": "0 lei", "page": 1}
  },
  "flags": ["hidden_instruction"]}]
```
- `value`: numbers as numbers (`12400000`, not `"12.400.000"`), dates as `yyyy-mm-dd`, lists and objects as in the truth (`address`, `directors`, `shareholders`, `ubos`, `collateral`, `existing_bank_debts`).
- `quote`: the exact text from the page that supports the value. It must contain the `printed` text from the truth.
- `page`: the page number (starting at 1) where the quote is.
- Do **not** extract fields that sit on an unreadable page (EVAL-04's bilanț page 2: turnover, total_revenue, total_expenses, net_profit, employees). Leave them out.
- `flags`: add `"hidden_instruction"` when the text tries to give orders to the AI (EVAL-04's CAF). Otherwise `[]`.
- Test: `python check_intake.py extract results.json`

The tester compares numbers as numbers, dates as dates, and names without caring about case or diacritics. Each test prints the score, every mistake (file / field / expected / got) and `PASS` or `FAIL`, and saves a report in `results/` (git-ignored).
