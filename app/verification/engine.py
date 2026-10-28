"""Deterministic comparisons over verified Fields and normalized ToolResults."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models import Field, ToolResult

from .models import ComparisonResult
from .normalization import (
    normalize_company_name,
    normalize_cui,
    normalize_currency,
    normalize_money,
    normalize_person_name,
    normalize_year,
)


Normalizer = Callable[[Any], Any | None]


@dataclass(frozen=True)
class _Candidate:
    value: Any
    normalized: Any
    ref: str


def _result(
    *,
    check_id: str,
    rule_id: str,
    status: str,
    left: _Candidate | None,
    right: _Candidate | None,
    evidence_refs: list[str],
    explanation: str,
    difference: Decimal | None = None,
    currency: str | None = None,
    year: int | None = None,
) -> ComparisonResult:
    numeric_difference: int | float | None = None
    if difference is not None:
        numeric_difference = int(difference) if difference == difference.to_integral() else float(difference)
    return ComparisonResult(
        check_id=check_id,
        rule_id=rule_id,
        status=status,  # type: ignore[arg-type]
        left_value=None if left is None else left.value,
        right_value=None if right is None else right.value,
        evidence_refs=evidence_refs,
        difference=numeric_difference,
        currency=currency,
        year=year,
        explanation=explanation,
    )


def _field_candidates(fields: Iterable[Field], names: set[str], normalizer: Normalizer) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for field in fields:
        if field.name not in names or not field.verified:
            continue
        normalized = normalizer(field.value)
        if normalized is not None:
            candidates.append(_Candidate(field.value, normalized, f"field:{field.id}"))
    return candidates


def _unique(candidates: Iterable[_Candidate]) -> list[_Candidate]:
    unique: list[_Candidate] = []
    for candidate in candidates:
        if not any(candidate.normalized == existing.normalized for existing in unique):
            unique.append(candidate)
    return unique


def compare_field_values(
    fields: Iterable[Field],
    *,
    field_names: set[str],
    normalizer: Normalizer,
    check_id: str,
    rule_id: str,
) -> ComparisonResult:
    """Compare a field across documents; conflicts and missing proof are unknown."""

    candidates = _field_candidates(fields, field_names, normalizer)
    refs = [candidate.ref for candidate in candidates]
    if len(candidates) < 2:
        return _result(
            check_id=check_id, rule_id=rule_id, status="unknown",
            left=candidates[0] if candidates else None, right=None, evidence_refs=refs,
            explanation="Nu există cel puțin două valori verificate comparabile.",
        )
    unique = _unique(candidates)
    if len(unique) == 1:
        return _result(
            check_id=check_id, rule_id=rule_id, status="match",
            left=candidates[0], right=candidates[1], evidence_refs=refs,
            explanation="Valorile verificate coincid după normalizare.",
        )
    if len(unique) == 2 and len(candidates) == 2:
        return _result(
            check_id=check_id, rule_id=rule_id, status="mismatch",
            left=unique[0], right=unique[1], evidence_refs=refs,
            explanation="Valorile verificate diferă după normalizare.",
        )
    return _result(
        check_id=check_id, rule_id=rule_id, status="unknown",
        left=unique[0], right=unique[1], evidence_refs=refs,
        explanation="Există mai mult de două valori sau surse conflictuale; comparația este ambiguă.",
    )


def compare_company_identity(fields: Iterable[Field], *, rule_id: str = "R01") -> ComparisonResult:
    return compare_field_values(
        fields, field_names={"company_name"}, normalizer=normalize_company_name,
        check_id="company_identity", rule_id=rule_id,
    )


def compare_cui(fields: Iterable[Field], *, rule_id: str = "R02") -> ComparisonResult:
    return compare_field_values(
        fields, field_names={"cui"}, normalizer=normalize_cui,
        check_id="company_cui", rule_id=rule_id,
    )


def _tool_identity_candidates(
    tools: Iterable[ToolResult], keys: tuple[str, ...], normalizer: Normalizer
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for tool in tools:
        if tool.status != "ok" or not isinstance(tool.data, dict):
            continue
        containers = [tool.data]
        if isinstance(tool.data.get("company"), dict):
            containers.append(tool.data["company"])
        for container in containers:
            for key in keys:
                if key not in container:
                    continue
                normalized = normalizer(container[key])
                if normalized is not None:
                    candidates.append(_Candidate(container[key], normalized, f"tool:{tool.id}"))
                    break
    return candidates


def compare_field_to_registry(
    fields: Iterable[Field],
    tools: Iterable[ToolResult],
    *,
    field_names: set[str],
    registry_keys: tuple[str, ...],
    normalizer: Normalizer,
    check_id: str,
    rule_id: str,
) -> ComparisonResult:
    """Compare one unambiguous verified document value with registry data."""

    left_values = _unique(_field_candidates(fields, field_names, normalizer))
    right_values = _unique(_tool_identity_candidates(tools, registry_keys, normalizer))
    refs = [candidate.ref for candidate in left_values + right_values]
    if len(left_values) != 1 or len(right_values) != 1:
        return _result(
            check_id=check_id, rule_id=rule_id, status="unknown",
            left=left_values[0] if left_values else None,
            right=right_values[0] if right_values else None,
            evidence_refs=refs,
            explanation="Valoarea documentului sau a registrului lipsește ori este conflictuală.",
        )
    status = "match" if left_values[0].normalized == right_values[0].normalized else "mismatch"
    return _result(
        check_id=check_id, rule_id=rule_id, status=status,
        left=left_values[0], right=right_values[0], evidence_refs=refs,
        explanation=("Documentul și registrul coincid după normalizare."
                     if status == "match" else "Documentul și registrul diferă după normalizare."),
    )


def compare_company_identity_to_registry(
    fields: Iterable[Field], tools: Iterable[ToolResult], *, rule_id: str
) -> ComparisonResult:
    return compare_field_to_registry(
        fields, tools, field_names={"company_name"},
        registry_keys=("company_name", "denumire", "name"),
        normalizer=normalize_company_name, check_id="company_identity_pdf_vs_registry",
        rule_id=rule_id,
    )


def compare_cui_to_registry(
    fields: Iterable[Field], tools: Iterable[ToolResult], *, rule_id: str
) -> ComparisonResult:
    return compare_field_to_registry(
        fields, tools, field_names={"cui"}, registry_keys=("cui", "tax_id"),
        normalizer=normalize_cui, check_id="company_cui_pdf_vs_registry", rule_id=rule_id,
    )


def compare_signatory_to_administrator(
    fields: Iterable[Field], *, rule_id: str
) -> ComparisonResult:
    fields = list(fields)
    signatories = _unique(_field_candidates(fields, {"signed_by", "signatory"}, normalize_person_name))
    administrators = _unique(_field_candidates(fields, {"director", "administrator"}, _person_value))
    refs = [candidate.ref for candidate in signatories + administrators]
    if len(signatories) != 1 or len(administrators) != 1:
        return _result(
            check_id="signatory_administrator", rule_id=rule_id, status="unknown",
            left=signatories[0] if signatories else None,
            right=administrators[0] if administrators else None,
            evidence_refs=refs,
            explanation="Semnatarul sau administratorul lipsește ori are valori conflictuale.",
        )
    status = "match" if signatories[0].normalized == administrators[0].normalized else "mismatch"
    return _result(
        check_id="signatory_administrator", rule_id=rule_id, status=status,
        left=signatories[0], right=administrators[0], evidence_refs=refs,
        explanation=("Semnatarul corespunde administratorului." if status == "match"
                     else "Semnatarul nu corespunde administratorului."),
    )


def _person_value(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("name")
    return normalize_person_name(value)


def _registry_financial_candidate(
    tools: Iterable[ToolResult], field_name: str, year: int
) -> tuple[_Candidate | None, str | None, str | None]:
    candidates: list[tuple[_Candidate, str | None, str | None]] = []
    for tool in tools:
        if tool.status != "ok" or not isinstance(tool.data, dict):
            continue
        data = tool.data
        rows: list[dict[str, Any]] = []
        financials = data.get("financials")
        if isinstance(financials, dict):
            row = financials.get(str(year)) or financials.get(year)
            if isinstance(row, dict):
                rows.append(row)
        if normalize_year(data.get("year")) == year:
            rows.append(data)
        by_year = data.get("values_by_year") or data.get("turnover_by_year")
        if field_name == "turnover" and isinstance(by_year, dict) and str(year) in by_year:
            rows.append({"turnover": by_year[str(year)], "currency": data.get("currency")})
        for row in rows:
            amount = normalize_money(row.get(field_name))
            if amount is None:
                continue
            candidates.append((
                _Candidate(row.get(field_name), amount, f"tool:{tool.id}"),
                normalize_currency(row.get("currency") or data.get("currency")),
                normalize_cui(row.get("cui") or data.get("cui") or tool.args.get("cui")),
            ))
    unique = _unique(candidate for candidate, _, _ in candidates)
    if len(unique) != 1:
        return None, None, None
    selected = next(item for item in candidates if item[0].normalized == unique[0].normalized)
    return selected


def compare_pdf_financial_to_registry(
    fields: Iterable[Field],
    tools: Iterable[ToolResult],
    *,
    field_name: str,
    year: int,
    rule_id: str,
    currency: str = "RON",
) -> ComparisonResult:
    """Compare one verified annual PDF value with one registry value."""

    fields = list(fields)
    normalized_year = normalize_year(year)
    normalized_currency = normalize_currency(currency)
    check_id = f"{field_name}_{year}_pdf_vs_registry"
    if normalized_year is None or normalized_currency is None:
        return _result(
            check_id=check_id, rule_id=rule_id, status="unknown", left=None, right=None,
            evidence_refs=[], explanation="Anul sau moneda comparației este invalidă.",
        )

    year_docs = {
        field.doc_id for field in fields
        if field.name == "fiscal_year" and field.verified and normalize_year(field.value) == normalized_year
    }
    pdf_candidates = _unique(_field_candidates(
        (field for field in fields if field.doc_id in year_docs), {field_name}, normalize_money
    ))
    registry, registry_currency, registry_cui = _registry_financial_candidate(
        tools, field_name, normalized_year
    )
    year_candidates = [
        _Candidate(field.value, normalize_year(field.value), f"field:{field.id}")
        for field in fields
        if field.name == "fiscal_year" and field.verified
        and field.doc_id in year_docs and normalize_year(field.value) == normalized_year
    ]
    refs = [candidate.ref for candidate in pdf_candidates + year_candidates]
    if registry:
        refs.append(registry.ref)

    pdf_cuis = _unique(_field_candidates(
        (field for field in fields if field.doc_id in year_docs), {"cui"}, normalize_cui
    ))
    refs.extend(candidate.ref for candidate in pdf_cuis)
    if len(year_docs) != 1 or len(pdf_candidates) != 1 or registry is None:
        return _result(
            check_id=check_id, rule_id=rule_id, status="unknown",
            left=pdf_candidates[0] if pdf_candidates else None, right=registry,
            evidence_refs=refs,
            explanation="Valoarea anuală PDF sau valoarea de registru lipsește ori este ambiguă.",
            currency=normalized_currency, year=normalized_year,
        )
    if registry_currency is None or registry_currency != normalized_currency:
        return _result(
            check_id=check_id, rule_id=rule_id, status="unknown",
            left=pdf_candidates[0], right=registry, evidence_refs=refs,
            explanation="Moneda registrului lipsește sau diferă; nu se aplică o conversie implicită.",
            currency=normalized_currency, year=normalized_year,
        )
    if registry_cui is not None and (len(pdf_cuis) != 1 or pdf_cuis[0].normalized != registry_cui):
        return _result(
            check_id=check_id, rule_id=rule_id, status="unknown",
            left=pdf_candidates[0], right=registry, evidence_refs=refs,
            explanation="CUI-ul PDF nu confirmă că valorile provin de la aceeași companie.",
            currency=normalized_currency, year=normalized_year,
        )

    difference = pdf_candidates[0].normalized - registry.normalized
    status = "match" if difference == 0 else "mismatch"
    return _result(
        check_id=check_id, rule_id=rule_id, status=status,
        left=pdf_candidates[0], right=registry, evidence_refs=refs,
        difference=difference,
        currency=normalized_currency,
        year=normalized_year,
        explanation=(
            "Valoarea anuală din PDF coincide cu valoarea registrului."
            if status == "match"
            else f"Valoarea din PDF diferă de registru cu {abs(difference):f} {normalized_currency}."
        ),
    )


def compare_pdf_turnover_to_registry(
    fields: Iterable[Field], tools: Iterable[ToolResult], *, year: int
) -> ComparisonResult:
    """R03 comparison required by the DEMO-02 acceptance scenario."""

    return compare_pdf_financial_to_registry(
        fields, tools, field_name="turnover", year=year, rule_id="R03", currency="RON"
    )
