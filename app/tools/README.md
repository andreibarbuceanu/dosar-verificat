# `app/tools`: Registry Tools (Sprint 2 — Rolul 2)

Layer-ul determinist de acces la registrele simulate (**ANAF Companie/TVA**, **ANAF Bilanț**, **ONRC**, **Portalul Instanțelor**).

- Reutilizează modelul Pydantic `ToolResult` din `app/models.py` (`extra="forbid"`).
- Folosește o arhitectură pluggable bazată pe `RegistryProvider` (`FixtureRegistryProvider` / `MockRegistryProvider`).
- Consumă fixturile din `fixtures/registry/` (create de Rolul 1). Dacă folderul `fixtures/registry/` nu este încă prezent pe disc, folosește substituenți sintetici locali (inclusiv pentru `DEMO-02` / CUI `41738203`).
- **Nu** efectuează interogări live și **nu** accesează `companies.json`, `expected/` sau `planted_errors`.
- Marchează explicit proveniența datelor prin `"source_mode": "simulated_fixture"` și păstrează `raw_ref` + `fetched_at`.

## Funcții publice

```python
from app.tools import (
    get_anaf_company,
    get_anaf_financials,
    get_onrc_company,
    get_court_cases,
    query_all_registries,
)

res_fin = get_anaf_financials("RO41738203", 2024)
# ToolResult(
#   id="tool-demo02-financials",
#   tool="anaf_financials",
#   args={"cui": "41738203", "year": 2024},
#   status="ok",
#   data={"cui": "41738203", "year": 2024, "turnover": 8100000, ...},
#   raw_ref="fixtures/registry/DEMO-02/anaf_financials.json",
#   fetched_at=datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc),
# )
```

| Funcție | `tool` în `ToolResult` | `args` | Ce returnează în `data` (`status="ok"`) |
|---|---|---|---|
| `get_anaf_company(cui)` | `"anaf_company"` | `{"cui": "<cui_norm>"}` | `cui`, `name`, `company_name`, `reg_com`, `address`, `active`, `inactive`, `vat_registered`, `vat_since`, `vat_cancelled`, `e_factura`, `split_vat`, `cash_vat`, `source_mode` |
| `get_anaf_financials(cui, year)` | `"anaf_financials"` | `{"cui": "<cui_norm>", "year": <int>}` | `cui`, `year`, `turnover`, `net_profit`, `total_revenue`, `total_expenses`, `fixed_assets`, `current_assets`, `total_assets`, `equity`, `liabilities`, `employees`, `currency`, `source_mode` |
| `get_onrc_company(cui)` | `"onrc_company"` | `{"cui": "<cui_norm>"}` | `cui`, `name`, `company_name`, `legal_form`, `reg_com`, `euid`, `registration_date`, `onrc_status`, `share_capital_lei`, `address`, `directors`, `shareholders`, `ubos`, `source_mode` |
| `get_court_cases(cui)` | `"court_cases"` | `{"cui": "<cui_norm>"}` | `cui`, `company_name`, `cases`, `court_cases`, `total_cases`, `open_cases_count`, `has_open_insolvency`, `has_open_enforcement`, `source_mode` |

## Tratarea stărilor (`status`)

- `"ok"`: Datele au fost găsite și validate/normalizate.
- `"not_found"`: CUI-ul este inexistent în fixturi, anul fiscal cerut nu este depus în `anaf_financials`, sau CUI-ul furnizat are un format invalid.
- `"unavailable"`: Sursa este marcată indisponibilă (`{"status": "unavailable"}`), fișierul fixture lipsește dintr-un dosar înregistrat în manifest, sau fișierul JSON este corupt/malformat. Mesajul de eroare este păstrat în `result.data["error"]`.

## Rulare teste

```bash
pytest tests/tools -q
```

