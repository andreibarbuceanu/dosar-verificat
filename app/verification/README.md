# Cross-document verification

This module compares already extracted, verified `Field` values with other
documents or normalized `ToolResult` data. It does not parse PDFs, call
registries, create findings, or decide case outcomes.

```python
from app.verification import compare_pdf_turnover_to_registry

comparison = compare_pdf_turnover_to_registry(fields, tool_results, year=2024)
payload = comparison.to_dict()
```

Identity checks can be performed across documents or against a successful
registry result:

```python
from app.verification import compare_company_identity, compare_cui_to_registry

document_name_check = compare_company_identity(fields, rule_id="R01")
registry_cui_check = compare_cui_to_registry(fields, tool_results, rule_id="R02")
```

`status` is `match`, `mismatch`, or `unknown`. Missing, unverified,
currency-incompatible, company-incompatible, or conflicting evidence produces
`unknown`. Evidence references use the shared `field:<id>` and `tool:<id>`
format.
