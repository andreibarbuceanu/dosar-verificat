"""app.tools — Layer-ul de acces la registrele simulate (Sprint 2, Rolul 2)."""

from __future__ import annotations

from .mock_provider import (
    DEFAULT_FIXTURES_DIR,
    DEFAULT_SIMULATED_TIMESTAMP,
    FixtureRegistryProvider,
    MockRegistryProvider,
    ProviderResponse,
    RegistryProvider,
)
from .normalization import (
    is_valid_cui_format,
    normalize_anaf_company_payload,
    normalize_anaf_financials_payload,
    normalize_company_name,
    normalize_court_cases_payload,
    normalize_cui,
    normalize_onrc_payload,
    normalize_person_name,
    normalize_text_value,
    validate_cui_checksum,
)
from .registry import (
    anaf_company,
    anaf_financials,
    court_cases,
    get_anaf_company,
    get_anaf_financials,
    get_court_cases,
    get_default_provider,
    get_onrc_company,
    onrc_company,
    query_all_registries,
    set_default_provider,
)

__all__ = [
    "DEFAULT_FIXTURES_DIR",
    "DEFAULT_SIMULATED_TIMESTAMP",
    "FixtureRegistryProvider",
    "MockRegistryProvider",
    "ProviderResponse",
    "RegistryProvider",
    "anaf_company",
    "anaf_financials",
    "court_cases",
    "get_anaf_company",
    "get_anaf_financials",
    "get_court_cases",
    "get_default_provider",
    "get_onrc_company",
    "is_valid_cui_format",
    "normalize_anaf_company_payload",
    "normalize_anaf_financials_payload",
    "normalize_company_name",
    "normalize_court_cases_payload",
    "normalize_cui",
    "normalize_onrc_payload",
    "normalize_person_name",
    "normalize_text_value",
    "onrc_company",
    "query_all_registries",
    "set_default_provider",
    "validate_cui_checksum",
]

