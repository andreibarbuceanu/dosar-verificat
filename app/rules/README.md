# app/rules: deterministic rules engine (Sprint 2, Role 4)

Reads verified Fields, registry ToolResults, Role 3's comparisons and the Document list, and
returns **exactly one `Finding` per rule R01..R15**. No model, no network, no clock, no ground
truth. The only I/O is loading `rules.yaml`.

## API

```python
from app.rules import evaluate_rules, rule_catalog, RulesConfigError

findings = evaluate_rules(
    case_id,
    fields,            # list[Field]
    tool_results,      # list[ToolResult]
    comparisons,       # Role 3 ComparisonResult objects or dicts (SPRINT2_CONTRACT §5.1)
    documents=None,    # list[Document]; needed for R14
    config_path=None,  # default app/rules/rules.yaml
) -> list[Finding]     # R01..R15 sorted, id = f"finding-{rule_id}-{case_id}", checker = "n/a"

rule_catalog() -> list[dict]
# {rule_id, description, severity, implemented, mandatory, inputs, thresholds}
```

- `implemented: false` rules are returned as `unknown` with an explanation starting
  `Neimplementat în Sprint 2:`. They are never `pass`.
- `evidence` holds only refs that exist in the inputs: `field:<id>`, `tool:<id>` and, for R14 only,
  `doc:<id>`. `pass` and `fail` always carry at least one ref, otherwise they become `unknown`.
- Severity: `fail` uses the rule's severity (R02 and R13 decide at run time), an evaluated
  `unknown` uses `defaults.unknown_severity` (amber), `pass` and deferred rules use the
  severity in `rules.yaml`.
- Evidence is trusted only if `Field.verified is True` and the `ToolResult.status` is `ok`.
  Conflicting values for the same field are `unknown`.

## Rules

| Rule | Checks | Source | Status |
|---|---|---|---|
| R01 | CUI check digit (weights 753217532) | fields `cui` | implemented |
| R02 | Identity agrees across documents and registries | comparisons `R02` | implemented (needs Role 3 to label identity checks `R02`) |
| R03 | Bilanț turnover == ANAF turnover, same CUI, year, currency | comparison `R03` + `anaf_financials` + `fiscal_year` | implemented |
| R04 | Bilanț net profit == ANAF net profit | comparison `R04` + `anaf_financials` | implemented, `unknown` until the comparison exists |
| R05 | total_assets == equity + liabilities (same document, Decimal) | fields | implemented |
| R06 | Company active at ANAF | `anaf_company.active` | implemented |
| R07 | No VAT cancellation in the last 12 months | `anaf_company.vat_cancelled` / `vat_since` + `application_date` | implemented, `unknown` when the registry has no cancellation data |
| R08 | CAF issued within 30 days of the application date | fields `caf_issue_date`, `application_date` | implemented |
| R09 | CAF shows no debts | field `caf_has_debts` (+ `caf_total_debt` for contradictions) | implemented |
| R10 | Directors on the application match ONRC | comparison `R10` + `onrc_company` | implemented, `unknown` until the comparison exists |
| R11 | Declared UBOs match shareholders >= 25% | comparison `R11` + `onrc_company` | implemented, `unknown` until the comparison exists |
| R12 | Sanctions screening | none | deferred: no source |
| R13 | No open insolvency / enforcement against the company (no score) | `court_cases` | implemented |
| R14 | Required documents present and readable | `documents` | implemented |
| R15 | No injected instructions in documents | none | deferred: no flag in the models |

Cross-source rules (R02, R03, R04, R10, R11) consume Role 3's comparisons; they never
recompute them. Mapping: all relevant comparisons `match` -> pass; any `mismatch` -> fail;
missing or `unknown` and no mismatch -> unknown. A comparison is set aside (-> unknown) when its
evidence does not exist, a field is unverified, a tool result is not `ok`, its value contradicts
the Field it cites, or (R03/R04) the fiscal year or currency differs.

### R13 policy

Only cases where the company is a party with certain identity count: CUI match when the case has
one; otherwise exact normalized name **and** same legal form; a case with no party data came from
a CUI query and is attributed to that CUI. Similar name, other legal form or other city -> `unknown`
("posibilă potrivire, verificare analist") with the case number. Open insolvency as debtor -> red
fail; open enforcement as debtor -> amber fail; only closed cases, creditor/plaintiff cases or no
cases -> pass (tool `ok` only). The engine ignores the summary flags in the registry data
(`has_open_*`) and reads the cases. No litigation score is computed.

## Changing a threshold

Edit `rules.yaml`. Each threshold is `{value, source, confirmed}`; `confirmed: true` only after the
mentors/lead approve it. The file is validated on every load (unknown keys, missing rules, bad
severities, missing thresholds raise `RulesConfigError`). To enable a deferred rule: write its
function in `definitions.py`, add it to `REGISTRY` and set `implemented: true`.

## Tests

```bash
python -m pytest tests/rules -q
```

Test doubles (valid `app.models` instances) live in `tests/rules/rules_factories.py`.
