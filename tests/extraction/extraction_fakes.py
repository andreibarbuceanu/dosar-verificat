"""Fake model and sample pages for extraction tests. No network, no account."""
from __future__ import annotations

# DEMO-02: AGRO NORD TRANS SRL. Turnover in the PDF is 12.400.000; ANAF says 8.100.000.
BILANT_PAGES = [
    """AGRO NORD TRANS SRL
CUI: RO41738203   Nr. ORC: J12/3456/2019
Sediul social: Str. Fabricii nr. 7, Cluj-Napoca, jud. Cluj
BILANȚ PRESCURTAT la 31.12.2024
Indicator                         2024          2023
Cifra de afaceri netă        12.400.000     9.750.000
Venituri totale              12.950.000    10.100.000
Cheltuieli totale            12.300.000     9.600.000
Profit net                      520.000       410.000
""",
    """Active imobilizate           3.200.000     2.900.000
Active circulante            4.100.000     3.600.000
Total active                 7.300.000     6.500.000
Capitaluri proprii           2.800.000     2.280.000
Datorii                      4.500.000     4.220.000
Număr mediu de salariați            38            35
""",
]


def f(name: str, value: str, page: int, quote: str) -> dict:
    return {"name": name, "value": value, "page": page, "quote": quote}


def person(kind: str, page: int, quote: str, name: str, role: str = "", percent: str = "",
           birth_date: str = "", nationality: str = "") -> dict:
    return {"kind": kind, "name": name, "role": role, "percent": percent,
            "birth_date": birth_date, "nationality": nationality, "page": page, "quote": quote}


BILANT_ANSWER = {
    "fields": [
        f("company_name", "AGRO NORD TRANS SRL", 1, "AGRO NORD TRANS SRL"),
        f("cui", "RO41738203", 1, "CUI: RO41738203"),
        f("reg_com_number", "J12/3456/2019", 1, "Nr. ORC: J12/3456/2019"),
        f("address", "Str. Fabricii nr. 7, Cluj-Napoca, jud. Cluj", 1,
          "Sediul social: Str. Fabricii nr. 7, Cluj-Napoca, jud. Cluj"),
        f("fiscal_year", "2024", 1, "Indicator 2024 2023"),
        f("turnover", "12.400.000", 1, "Cifra de afaceri netă 12.400.000 9.750.000"),
        f("total_revenue", "12.950.000", 1, "Venituri totale 12.950.000"),
        f("total_expenses", "12.300.000", 1, "Cheltuieli totale 12.300.000"),
        f("net_profit", "520.000", 1, "Profit net 520.000"),
        f("fixed_assets", "3.200.000", 2, "Active imobilizate 3.200.000"),
        f("current_assets", "4.100.000", 2, "Active circulante 4.100.000"),
        f("total_assets", "7.300.000", 2, "Total active 7.300.000"),
        f("equity", "2.800.000", 2, "Capitaluri proprii 2.800.000"),
        f("liabilities", "4.500.000", 2, "Datorii 4.500.000"),
        f("employees", "38", 2, "Număr mediu de salariați 38"),
    ],
    "people": [],
    "not_found": [],
    "injection_suspected": [],
}


class FakeModel:
    """complete(prompt, schema) -> canned answer; records every call."""

    def __init__(self, answer: dict):
        self.answer = answer
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, prompt: str, schema: dict) -> dict:
        self.calls.append((prompt, schema))
        return self.answer


def answer(fields=(), people=(), injection=()) -> dict:
    return {"fields": list(fields), "people": list(people), "not_found": [],
            "injection_suspected": list(injection)}
