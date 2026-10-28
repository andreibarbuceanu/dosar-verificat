"""Layer-ul public de acces la registrele simulate pentru Sprint 2 (Rolul 2: Registry Tools).

Expune:
- `get_anaf_company(cui: str) -> ToolResult`
- `get_anaf_financials(cui: str, year: int) -> ToolResult`
- `get_onrc_company(cui: str) -> ToolResult`
- `get_court_cases(cui: str) -> ToolResult`

Reutilizează modelul Pydantic `ToolResult` din `app.models` și nu efectuează apeluri live.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models import ToolResult

from .mock_provider import (
    DEFAULT_SIMULATED_TIMESTAMP,
    FixtureRegistryProvider,
    ProviderResponse,
    RegistryProvider,
)
from .normalization import (
    normalize_anaf_company_payload,
    normalize_anaf_financials_payload,
    normalize_court_cases_payload,
    normalize_cui,
    normalize_onrc_payload,
)

_DEFAULT_PROVIDER: RegistryProvider | None = None


def get_default_provider() -> RegistryProvider:
    """Returnează providerul activ (implicit `FixtureRegistryProvider`)."""
    global _DEFAULT_PROVIDER
    if _DEFAULT_PROVIDER is None:
        _DEFAULT_PROVIDER = FixtureRegistryProvider()
    return _DEFAULT_PROVIDER


def set_default_provider(provider: RegistryProvider | None) -> None:
    """Permite injectarea unui provider custom în teste sau în orchestratorul de integrare."""
    global _DEFAULT_PROVIDER
    _DEFAULT_PROVIDER = provider


def _resolve_provider(
    provider: RegistryProvider | None, fixtures_dir: str | Path | None
) -> RegistryProvider:
    if provider is not None:
        return provider
    if fixtures_dir is not None:
        return FixtureRegistryProvider(fixtures_dir=fixtures_dir, allow_builtin_fallback=False)
    return get_default_provider()


def _make_tool_id(case_id: str | None, cui_or_raw: str, suffix: str) -> str:
    """Generează un ID determinist conform SPRINT2_CONTRACT.md (ex. `tool-demo02-financials`)."""
    base = (case_id or cui_or_raw or "unknown").strip().lower()
    slug = "".join(ch for ch in base if ch.isalnum()) or "unknown"
    return f"tool-{slug}-{suffix}"


def _build_error_tool_result(
    *,
    tool_id: str,
    tool_name: str,
    args: dict[str, Any],
    resp: ProviderResponse | None,
    status: str,
    error_message: str,
) -> ToolResult:
    return ToolResult(
        id=tool_id,
        tool=tool_name,
        args=args,
        status=status,  # type: ignore[arg-type]
        data={
            "error": error_message,
            "source_mode": "simulated_fixture",
        },
        raw_ref=resp.raw_ref if resp else None,
        fetched_at=resp.fetched_at if resp else DEFAULT_SIMULATED_TIMESTAMP,
    )


def get_anaf_company(
    cui: str,
    *,
    provider: RegistryProvider | None = None,
    fixtures_dir: str | Path | None = None,
) -> ToolResult:
    """Interoghează registrul simulat ANAF pentru datele de identificare și TVA ale companiei."""
    raw_cui_str = str(cui).strip() if cui is not None else ""
    try:
        norm_cui = normalize_cui(cui)
    except ValueError as exc:
        return _build_error_tool_result(
            tool_id=_make_tool_id(None, raw_cui_str, "anaf-company"),
            tool_name="anaf_company",
            args={"cui": raw_cui_str},
            resp=None,
            status="not_found",
            error_message=str(exc),
        )

    active_provider = _resolve_provider(provider, fixtures_dir)
    resp = active_provider.fetch_anaf_company(norm_cui)
    tool_id = _make_tool_id(resp.case_id, norm_cui, "anaf-company")
    args = {"cui": norm_cui}

    if resp.status != "ok":
        return _build_error_tool_result(
            tool_id=tool_id,
            tool_name="anaf_company",
            args=args,
            resp=resp,
            status=resp.status,
            error_message=resp.error or f"Status registru ANAF: {resp.status}",
        )

    try:
        normalized_data = normalize_anaf_company_payload(resp.payload, norm_cui)
    except Exception as exc:
        return _build_error_tool_result(
            tool_id=tool_id,
            tool_name="anaf_company",
            args=args,
            resp=resp,
            status="unavailable",
            error_message=f"Răspuns malformat în anaf_company: {exc}",
        )

    return ToolResult(
        id=tool_id,
        tool="anaf_company",
        args=args,
        status="ok",
        data=normalized_data,
        raw_ref=resp.raw_ref,
        fetched_at=resp.fetched_at,
    )


def get_anaf_financials(
    cui: str,
    year: int,
    *,
    provider: RegistryProvider | None = None,
    fixtures_dir: str | Path | None = None,
) -> ToolResult:
    """Interoghează registrul simulat ANAF pentru indicatorii financiari anuali depuși."""
    raw_cui_str = str(cui).strip() if cui is not None else ""
    try:
        year_int = int(year)
        if isinstance(year, bool) or not (1990 <= year_int <= 2100):
            raise ValueError(f"An fiscal invalid: {year!r}")
    except (ValueError, TypeError) as exc:
        return _build_error_tool_result(
            tool_id=_make_tool_id(None, raw_cui_str, "financials"),
            tool_name="anaf_financials",
            args={"cui": raw_cui_str, "year": year},
            resp=None,
            status="not_found",
            error_message=f"An fiscal invalid: {exc}",
        )

    try:
        norm_cui = normalize_cui(cui)
    except ValueError as exc:
        return _build_error_tool_result(
            tool_id=_make_tool_id(None, raw_cui_str, "financials"),
            tool_name="anaf_financials",
            args={"cui": raw_cui_str, "year": year_int},
            resp=None,
            status="not_found",
            error_message=str(exc),
        )

    active_provider = _resolve_provider(provider, fixtures_dir)
    resp = active_provider.fetch_anaf_financials(norm_cui, year_int)
    tool_id = _make_tool_id(resp.case_id, norm_cui, "financials")
    args = {"cui": norm_cui, "year": year_int}

    if resp.status != "ok":
        return _build_error_tool_result(
            tool_id=tool_id,
            tool_name="anaf_financials",
            args=args,
            resp=resp,
            status=resp.status,
            error_message=resp.error or f"Status registru ANAF Bilanț: {resp.status}",
        )

    try:
        normalized_data = normalize_anaf_financials_payload(
            resp.payload, norm_cui, year_int
        )
    except Exception as exc:
        return _build_error_tool_result(
            tool_id=tool_id,
            tool_name="anaf_financials",
            args=args,
            resp=resp,
            status="unavailable",
            error_message=f"Răspuns malformat în anaf_financials: {exc}",
        )

    if normalized_data is None:
        return _build_error_tool_result(
            tool_id=tool_id,
            tool_name="anaf_financials",
            args=args,
            resp=resp,
            status="not_found",
            error_message=f"Nu există bilanț depus la ANAF pentru CUI {norm_cui} în anul {year_int}.",
        )

    return ToolResult(
        id=tool_id,
        tool="anaf_financials",
        args=args,
        status="ok",
        data=normalized_data,
        raw_ref=resp.raw_ref,
        fetched_at=resp.fetched_at,
    )


def get_onrc_company(
    cui: str,
    *,
    provider: RegistryProvider | None = None,
    fixtures_dir: str | Path | None = None,
) -> ToolResult:
    """Interoghează registrul simulat ONRC pentru identitatea companiei, administratori și asociați."""
    raw_cui_str = str(cui).strip() if cui is not None else ""
    try:
        norm_cui = normalize_cui(cui)
    except ValueError as exc:
        return _build_error_tool_result(
            tool_id=_make_tool_id(None, raw_cui_str, "onrc"),
            tool_name="onrc_company",
            args={"cui": raw_cui_str},
            resp=None,
            status="not_found",
            error_message=str(exc),
        )

    active_provider = _resolve_provider(provider, fixtures_dir)
    resp = active_provider.fetch_onrc_company(norm_cui)
    tool_id = _make_tool_id(resp.case_id, norm_cui, "onrc")
    args = {"cui": norm_cui}

    if resp.status != "ok":
        return _build_error_tool_result(
            tool_id=tool_id,
            tool_name="onrc_company",
            args=args,
            resp=resp,
            status=resp.status,
            error_message=resp.error or f"Status registru ONRC: {resp.status}",
        )

    try:
        normalized_data = normalize_onrc_payload(resp.payload, norm_cui)
    except Exception as exc:
        return _build_error_tool_result(
            tool_id=tool_id,
            tool_name="onrc_company",
            args=args,
            resp=resp,
            status="unavailable",
            error_message=f"Răspuns malformat în onrc: {exc}",
        )

    return ToolResult(
        id=tool_id,
        tool="onrc_company",
        args=args,
        status="ok",
        data=normalized_data,
        raw_ref=resp.raw_ref,
        fetched_at=resp.fetched_at,
    )


def get_court_cases(
    cui: str,
    *,
    provider: RegistryProvider | None = None,
    fixtures_dir: str | Path | None = None,
) -> ToolResult:
    """Interoghează registrul simulat al instanțelor (portal.just.ro) pentru litigii asociate CUI-ului."""
    raw_cui_str = str(cui).strip() if cui is not None else ""
    try:
        norm_cui = normalize_cui(cui)
    except ValueError as exc:
        return _build_error_tool_result(
            tool_id=_make_tool_id(None, raw_cui_str, "court-cases"),
            tool_name="court_cases",
            args={"cui": raw_cui_str},
            resp=None,
            status="not_found",
            error_message=str(exc),
        )

    active_provider = _resolve_provider(provider, fixtures_dir)
    resp = active_provider.fetch_court_cases(norm_cui)
    tool_id = _make_tool_id(resp.case_id, norm_cui, "court-cases")
    args = {"cui": norm_cui}

    if resp.status != "ok":
        return _build_error_tool_result(
            tool_id=tool_id,
            tool_name="court_cases",
            args=args,
            resp=resp,
            status=resp.status,
            error_message=resp.error or f"Status registru litigii: {resp.status}",
        )

    try:
        normalized_data = normalize_court_cases_payload(resp.payload, norm_cui)
    except Exception as exc:
        return _build_error_tool_result(
            tool_id=tool_id,
            tool_name="court_cases",
            args=args,
            resp=resp,
            status="unavailable",
            error_message=f"Răspuns malformat în court_cases: {exc}",
        )

    return ToolResult(
        id=tool_id,
        tool="court_cases",
        args=args,
        status="ok",
        data=normalized_data,
        raw_ref=resp.raw_ref,
        fetched_at=resp.fetched_at,
    )


def query_all_registries(
    cui: str,
    year: int = 2024,
    *,
    provider: RegistryProvider | None = None,
    fixtures_dir: str | Path | None = None,
) -> list[ToolResult]:
    """Interoghează toate cele 4 registre simulate pentru un CUI și un an financiar."""
    return [
        get_anaf_company(cui, provider=provider, fixtures_dir=fixtures_dir),
        get_anaf_financials(cui, year, provider=provider, fixtures_dir=fixtures_dir),
        get_onrc_company(cui, provider=provider, fixtures_dir=fixtures_dir),
        get_court_cases(cui, provider=provider, fixtures_dir=fixtures_dir),
    ]


# Alias-uri pentru compatibilitate cu denumirile scurte din ToolResult.tool
anaf_company = get_anaf_company
anaf_financials = get_anaf_financials
onrc_company = get_onrc_company
court_cases = get_court_cases
