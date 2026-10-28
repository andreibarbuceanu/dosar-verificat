"""Public API for deterministic cross-document verification."""

from .engine import (
    compare_company_identity,
    compare_company_identity_to_registry,
    compare_cui,
    compare_cui_to_registry,
    compare_field_to_registry,
    compare_field_values,
    compare_pdf_financial_to_registry,
    compare_pdf_turnover_to_registry,
    compare_signatory_to_administrator,
)
from .models import ComparisonResult, ComparisonStatus
from .normalization import (
    normalize_company_name,
    normalize_cui,
    normalize_currency,
    normalize_date,
    normalize_money,
    normalize_person_name,
    normalize_year,
)

__all__ = [
    "ComparisonResult",
    "ComparisonStatus",
    "compare_company_identity",
    "compare_company_identity_to_registry",
    "compare_cui",
    "compare_cui_to_registry",
    "compare_field_to_registry",
    "compare_field_values",
    "compare_pdf_financial_to_registry",
    "compare_pdf_turnover_to_registry",
    "compare_signatory_to_administrator",
    "normalize_company_name",
    "normalize_cui",
    "normalize_currency",
    "normalize_date",
    "normalize_money",
    "normalize_person_name",
    "normalize_year",
]
