"""Conservative label-based extraction when no recorded/live LLM is available.

This parser only copies values adjacent to known Romanian document labels.  The
normal extraction validator still verifies every value against its literal
quote, so this fallback cannot manufacture positive evidence.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(ch for ch in value if not unicodedata.combining(ch)).split())


def deterministic_payload(doc_type: str, pages: list[str]) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []

    def add(name: str, value: Any, page: int, quote: str) -> None:
        if value not in (None, "") and not any(item["name"] == name for item in fields):
            fields.append({"name": name, "value": value, "page": page, "quote": quote})

    def adjacent(name: str, labels: tuple[str, ...], *, last_of: int = 1) -> None:
        wanted = tuple(_norm(label) for label in labels)
        for page_no, text in enumerate(pages, start=1):
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            for index, line in enumerate(lines):
                normalized = _norm(line)
                match = next((label for label in wanted if normalized.startswith(label)), None)
                if match is None:
                    continue
                remainder = line.split(":", 1)[1].strip() if ":" in line else ""
                if remainder:
                    add(name, remainder, page_no, line)
                    return
                values = lines[index + 1:index + 1 + last_of]
                if values:
                    add(name, values[-1], page_no, "\n".join([line, *values]))
                    return

    # Common identity. Inline financial headings need dedicated parsing.
    adjacent("company_name", ("Denumire", "Entitate", "Contribuabil", "Persoana juridică"))
    adjacent("cui", ("Cod unic de înregistrare (CUI)", "Cod unic de înregistrare",
                      "Cod de identificare fiscală", "CUI"))
    adjacent("reg_com_number", ("Nr. Registrul Comerțului", "Număr de ordine în Registrul Comerțului",
                                 "Nr. Reg. Com."))
    adjacent("address", ("Sediu social", "Sediul social", "Domiciliul fiscal", "Adresa"))

    for page_no, text in enumerate(pages, start=1):
        for line in text.splitlines():
            if " | " not in line:
                continue
            name = re.search(r"Entitate:\s*([^|]+)", line, re.I)
            cui = re.search(r"CUI:\s*(RO)?\s*(\d{6,10})", line, re.I)
            reg = re.search(r"Nr\.\s*Reg\.\s*Com\.:\s*([^|]+)", line, re.I)
            if name:
                add("company_name", name.group(1).strip(), page_no, line.strip())
            if cui:
                add("cui", cui.group(2), page_no, line.strip())
            if reg:
                add("reg_com_number", reg.group(1).strip(), page_no, line.strip())

    if doc_type == "application":
        adjacent("application_date", ("Data",))
        adjacent("credit_product", ("Produs",))
        adjacent("requested_amount", ("Suma solicitată",))
        adjacent("currency", ("Suma solicitată",))
        adjacent("term_months", ("Durata",))
        adjacent("credit_purpose", ("Scopul finanțării", "Destinația creditului"))
        adjacent("collateral_value", ("Garanții propuse",))
        adjacent("existing_bank_debt", ("Datorii bancare existente",))
        adjacent("signed_by", ("Nume și semnătură",))
    elif doc_type == "bilant":
        adjacent("fiscal_year", ("Exercițiul financiar",))
        for name, labels in (
            ("fixed_assets", ("Active imobilizate",)),
            ("current_assets", ("Active circulante",)),
            ("total_assets", ("TOTAL ACTIVE",)),
            ("equity", ("Capitaluri proprii",)),
            ("liabilities", ("Datorii",)),
            ("turnover", ("Cifra de afaceri netă",)),
            ("total_revenue", ("Venituri totale",)),
            ("total_expenses", ("Cheltuieli totale",)),
            ("net_profit", ("Profitul net al exercițiului", "Pierderea netă a exercițiului")),
            ("employees", ("Număr mediu de salariați",)),
        ):
            adjacent(name, labels, last_of=2)
    elif doc_type == "caf":
        adjacent("caf_issue_date", ("Data eliberării",))
        adjacent("caf_total_debt", ("Total obligații restante",))
        for page_no, text in enumerate(pages, start=1):
            number = re.search(r"CERTIFICAT DE ATESTARE FISCALĂ\s+nr\.\s*([^\n]+)", text, re.I)
            issuer = re.search(r"Emitent:\s*([^\n|]+)", text, re.I)
            no_debt = re.search(r"[^\n]*nu înregistrează obligații fiscale restante[^\n]*", text, re.I)
            if number:
                add("caf_number", number.group(1).strip(), page_no, number.group(0).strip())
            if issuer:
                add("caf_issued_by", issuer.group(1).strip(), page_no, issuer.group(0).strip())
            if no_debt:
                add("caf_has_debts", False, page_no, no_debt.group(0).strip())
    elif doc_type == "onrc":
        adjacent("euid", ("EUID",))
        adjacent("registration_date", ("Data înregistrării",))
        adjacent("caen_code", ("Activitate principală (CAEN)", "Cod CAEN"))
        adjacent("share_capital", ("Capital social subscris și vărsat", "Capital social"))
        adjacent("onrc_status", ("Starea firmei",))

    return {"fields": fields, "people": [], "not_found": [], "injection_suspected": []}
