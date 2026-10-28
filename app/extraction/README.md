# app/extraction: AI Extraction (pipeline step 4)

Pages of text + document type → structured **Fields**, each with proof (page + exact quote).
**The model copies, the code decides.** A value without proof never enters the pipeline.

## API

```python
from app.extraction import extract_document, extract_pdf

result = extract_document(doc_id, doc_type, pages, complete=None)
result.to_dict()   # JSON-serializable
```

- `pages`: text per page, `pages[0]` = page 1. `""` (scanned/unreadable) pages are ignored.
  If every page is empty, the model is not called and every field is `not_found`.
- `doc_type`: `application | bilant | caf | onrc | ubo | unknown` (anything else → `unknown`).
- `complete(prompt, schema) -> dict`: the model. Defaults to `app.llm.complete` (imported
  lazily; backend chosen by `LLM_BACKEND=cli|api|replay`). Tests inject a fake.

`ExtractionResult`:

| key | content |
| --- | --- |
| `fields` | `[{name, value, doc_id, page, quote, verified: true}]`, CONTRACT `Field`; only verified values. `quote` is the exact page text (not the model's copy), so the UI can highlight it |
| `dropped` | `[{name, value, page, quote, reason}]`: what the model proposed and the code refused |
| `not_found` | field names (and person kinds) of this type with no verified value |
| `injection_suspected` | `[{page, text}]`: lines addressed to an AI (code regex + model reports that are really on the page) |
| `prompt_version` | `extract-v1` |

Values: `money/int/percent` → number (int when whole, negative for losses), `date` → `"YYYY-MM-DD"`,
`year` → int, `bool` → bool, `code` → digits string (CUI without `RO`), `text` → cleaned string
(comma diacritics ș/ț). People: one Field per person, `name` = `director | shareholder | ubo`,
`value` = dict; a sub-field not written in the document is `null`.

## Fields per type (`fields.py`)

Every type: `company_name` text, `cui` code, `reg_com_number` text, `address` text.

| type | fields | people |
| --- | --- | --- |
| application | application_date date, credit_product text, requested_amount money, currency text, term_months int, credit_purpose text, collateral_value money, existing_bank_debt money, signed_by text | director {name, role} |
| bilant | fiscal_year year, turnover, total_revenue, total_expenses, net_profit (negative = loss), fixed_assets, current_assets, total_assets, equity, liabilities (money), employees int | |
| caf | caf_number text, caf_issued_by text, caf_issue_date date, caf_has_debts bool, caf_total_debt money | |
| onrc | euid text, legal_form text, registration_date date, caen_code code, share_capital money, onrc_status text | director, shareholder {name, percent} |
| ubo | | ubo {name, birth_date, nationality, percent} |
| unknown | common only | director, shareholder, ubo |

## What the code checks (in order)

| reason | when |
| --- | --- |
| `unknown_field` | name not in this type's list (or person kind not allowed for the type) |
| `page_out_of_range` | page not an integer in `1..len(pages)` |
| `quote_not_on_page` | quote not on the given page after normalization, and not on exactly one other page (if it is, the page is corrected) |
| `unparseable_value` | value cannot be parsed for its kind; nothing is guessed (`"12.400 mii lei"`, `"38,5"` employees) |
| `value_not_in_quote` | parsed value not in the quote: numbers (with sign), dates, year, CUI/CAEN digits, text substring; for people the name (diacritics-insensitive) plus percent/birth_date |

Normalization for matching: NFC, ş/ţ (cedilla) → ș/ț (comma), NBSP/thin spaces → space,
typographic quotes/dashes → ASCII, soft hyphen removed, whitespace collapsed, casefold.
Numbers: `12.400.000`, `12 400 000`, `12,400,000`, `1.234,56`, `-123.000`, `(123.000)`,
`lei/RON/EUR/%` stripped. Dates: `dd.mm.yyyy`, `dd/mm/yyyy`, `dd-mm-yyyy`, `yyyy-mm-dd`,
`14 octombrie 2026`.

Identical values of a field are deduplicated; **different values are all kept** (the rules decide).
`caf_has_debts` is a reading of a sentence: the quote must be on the page, but the yes/no is not
string-matched. `role`/`nationality` are kept only if they appear in the quote, otherwise `null`.

## Run

```bash
pytest tests/extraction -q
python -m app.extraction file.pdf --type bilant                 # needs app.llm (LLM_BACKEND=replay|cli|api)
python -m app.extraction file.pdf --type bilant --print-prompt  # no model call
python tests/extraction/extraction_demo_pdf.py demo02.pdf       # DEMO-02 balance sheet PDF
```

Dependencies: `pymupdf` (PDF text, local testing only), `reportlab` and `pytest` (tests).
