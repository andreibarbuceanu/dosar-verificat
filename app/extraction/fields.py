"""The fields extracted per document type. Single source of truth for names and kinds.

kind decides how the code parses the raw text the model copied:
text | code | money | int | percent | date | bool | year
"""
from __future__ import annotations

from dataclasses import dataclass

DOC_TYPES = ("application", "bilant", "caf", "onrc", "ubo", "unknown")
KINDS = ("text", "code", "money", "int", "percent", "date", "bool", "year")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: str
    description: str


# On every document, so R01/R02 can compare identity across documents.
COMMON = (
    FieldSpec("company_name", "text", "Company name as written, e.g. 'AGRO NORD TRANS SRL'"),
    FieldSpec("cui", "code", "Fiscal code CUI/CIF (cod unic de inregistrare), with or without the RO prefix"),
    FieldSpec("reg_com_number", "text", "Trade register number (nr. ORC), e.g. 'J40/1234/2020'"),
    FieldSpec("address", "text", "Registered office address (sediul social)"),
)

SPECIFIC: dict[str, tuple[FieldSpec, ...]] = {
    "application": (
        FieldSpec("application_date", "date", "Date of the credit application"),
        FieldSpec("credit_product", "text", "Requested credit product, e.g. 'linie de credit'"),
        FieldSpec("requested_amount", "money", "Requested credit amount"),
        FieldSpec("currency", "text", "Currency of the requested amount, e.g. 'RON', 'EUR'"),
        FieldSpec("term_months", "int", "Credit term in months"),
        FieldSpec("credit_purpose", "text", "Stated purpose of the credit (scopul creditului)"),
        FieldSpec("collateral_value", "money", "Value of the offered collateral (garantii)"),
        FieldSpec("existing_bank_debt", "money", "Existing debt to banks declared by the applicant"),
        FieldSpec("signed_by", "text", "Name of the person who signed the application"),
    ),
    "bilant": (
        FieldSpec("fiscal_year", "year", "Most recent financial year in the balance sheet"),
        FieldSpec("turnover", "money", "Net turnover (cifra de afaceri neta), most recent year"),
        FieldSpec("total_revenue", "money", "Total revenue (venituri totale), most recent year"),
        FieldSpec("total_expenses", "money", "Total expenses (cheltuieli totale), most recent year"),
        FieldSpec("net_profit", "money", "Net profit or loss (profit/pierdere neta), most recent year; a loss is negative"),
        FieldSpec("fixed_assets", "money", "Fixed assets (active imobilizate), most recent year"),
        FieldSpec("current_assets", "money", "Current assets (active circulante), most recent year"),
        FieldSpec("total_assets", "money", "Total assets (total active), most recent year"),
        FieldSpec("equity", "money", "Equity (capitaluri proprii), most recent year"),
        FieldSpec("liabilities", "money", "Liabilities / debts (datorii), most recent year"),
        FieldSpec("employees", "int", "Average number of employees (numar mediu de salariati), most recent year"),
    ),
    "caf": (
        FieldSpec("caf_number", "text", "Number of the tax certificate (certificat de atestare fiscala)"),
        FieldSpec("caf_issued_by", "text", "Issuing tax authority, e.g. 'ANAF - DGRFP Bucuresti'"),
        FieldSpec("caf_issue_date", "date", "Issue date of the certificate"),
        FieldSpec("caf_has_debts", "bool", "Whether the certificate states outstanding tax debts: 'true' or 'false'"),
        FieldSpec("caf_total_debt", "money", "Total outstanding tax debt stated in the certificate"),
    ),
    "onrc": (
        FieldSpec("euid", "text", "European unique identifier (EUID), e.g. 'ROONRC.J40/1234/2020'"),
        FieldSpec("legal_form", "text", "Legal form, e.g. 'SRL', 'SA'"),
        FieldSpec("registration_date", "date", "Registration date at the trade register"),
        FieldSpec("caen_code", "code", "Main activity CAEN code, digits only, e.g. '4941'"),
        FieldSpec("share_capital", "money", "Subscribed share capital (capital social)"),
        FieldSpec("onrc_status", "text", "Company status, e.g. 'functiune', 'radiata', 'insolventa'"),
    ),
    "ubo": (),
    "unknown": (),
}

# One Field per person; value is a dict with exactly these keys.
PERSON_KINDS: dict[str, tuple[str, ...]] = {
    "director": ("name", "role"),
    "shareholder": ("name", "percent"),
    "ubo": ("name", "birth_date", "nationality", "percent"),
}

PEOPLE: dict[str, tuple[str, ...]] = {
    "application": ("director",),
    "bilant": (),
    "caf": (),
    "onrc": ("director", "shareholder"),
    "ubo": ("ubo",),
    "unknown": ("director", "shareholder", "ubo"),
}


def normalize_type(doc_type: str) -> str:
    """Anything outside the contract enum is treated as 'unknown'."""
    return doc_type if doc_type in DOC_TYPES else "unknown"


def fields_for(doc_type: str) -> tuple[FieldSpec, ...]:
    return COMMON + SPECIFIC[normalize_type(doc_type)]


def people_for(doc_type: str) -> tuple[str, ...]:
    return PEOPLE[normalize_type(doc_type)]


def expected_names(doc_type: str) -> list[str]:
    """Every name a Field of this document type can have, in display order."""
    return [f.name for f in fields_for(doc_type)] + list(people_for(doc_type))
