from datetime import datetime, timezone
import json
import unittest

from app.models import Field, ToolResult
from app.verification import (
    compare_company_identity,
    compare_company_identity_to_registry,
    compare_cui,
    compare_cui_to_registry,
    compare_pdf_financial_to_registry,
    compare_pdf_turnover_to_registry,
    compare_signatory_to_administrator,
)


def field(
    field_id: str,
    name: str,
    value: object,
    doc_id: str,
    *,
    verified: bool = True,
) -> Field:
    return Field(
        id=field_id,
        name=name,
        value=value,
        doc_id=doc_id,
        page=1,
        quote=f"Evidence for {name}: {value}",
        verified=verified,
    )


def tool(
    tool_id: str = "anaf-fin-1",
    *,
    status: str = "ok",
    data: dict | None = None,
) -> ToolResult:
    return ToolResult(
        id=tool_id,
        tool="anaf_financials",
        args={"cui": "41738200"},
        status=status,
        data=data,
        fetched_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )


def demo02_fields() -> list[Field]:
    return [
        field("f-cui", "cui", "RO41738200", "bilant-2024"),
        field("f-year", "fiscal_year", 2024, "bilant-2024"),
        field("f-turnover", "turnover", 12_400_000, "bilant-2024"),
    ]


class CrossDocumentTests(unittest.TestCase):
    def test_company_identity_matches_after_normalization(self) -> None:
        result = compare_company_identity([
            field("f1", "company_name", "AGRO NORD TRANS S.R.L.", "application"),
            field("f2", "company_name", "Agro Nord Trans SRL", "onrc"),
        ])
        self.assertEqual("match", result.status)
        self.assertEqual(["field:f1", "field:f2"], result.evidence_refs)

    def test_company_identity_mismatch(self) -> None:
        result = compare_company_identity([
            field("f1", "company_name", "AGRO NORD TRANS SRL", "application"),
            field("f2", "company_name", "AGRO SUD TRANS SRL", "onrc"),
        ])
        self.assertEqual("mismatch", result.status)

    def test_cui_matches_with_ro_prefix(self) -> None:
        result = compare_cui([
            field("f1", "cui", "RO41738200", "application"),
            field("f2", "cui", "41.738.200", "caf"),
        ])
        self.assertEqual("match", result.status)

    def test_company_identity_matches_nested_registry_response(self) -> None:
        fields = [field("name", "company_name", "AGRO NORD TRANS S.R.L.", "onrc")]
        registry = tool(data={"company": {"denumire": "Agro Nord Trans SRL"}})
        result = compare_company_identity_to_registry(fields, [registry], rule_id="R01")
        self.assertEqual("match", result.status)
        self.assertEqual(["field:name", "tool:anaf-fin-1"], result.evidence_refs)

    def test_cui_registry_mismatch(self) -> None:
        fields = [field("cui", "cui", "RO41738200", "onrc")]
        registry = tool(data={"company": {"cui": "99999999"}})
        result = compare_cui_to_registry(fields, [registry], rule_id="R02")
        self.assertEqual("mismatch", result.status)

    def test_unavailable_registry_identity_is_unknown(self) -> None:
        fields = [field("cui", "cui", "41738200", "onrc")]
        result = compare_cui_to_registry(fields, [tool(status="unavailable")], rule_id="R02")
        self.assertEqual("unknown", result.status)

    def test_unverified_field_never_creates_match(self) -> None:
        result = compare_cui([
            field("f1", "cui", "41738200", "application"),
            field("f2", "cui", "41738200", "caf", verified=False),
        ])
        self.assertEqual("unknown", result.status)
        self.assertEqual(["field:f1"], result.evidence_refs)

    def test_missing_value_is_unknown(self) -> None:
        result = compare_company_identity([])
        self.assertEqual("unknown", result.status)

    def test_three_conflicting_sources_are_ambiguous(self) -> None:
        result = compare_cui([
            field("f1", "cui", "41738200", "application"),
            field("f2", "cui", "41738200", "caf"),
            field("f3", "cui", "99999999", "onrc"),
        ])
        self.assertEqual("unknown", result.status)

    def test_signatory_matches_administrator_despite_name_order(self) -> None:
        result = compare_signatory_to_administrator([
            field("signed", "signed_by", "Andrei Mureșan", "application"),
            field("admin", "director", {"name": "Mureșan Andrei"}, "onrc"),
        ], rule_id="R04")
        self.assertEqual("match", result.status)
        self.assertEqual(["field:signed", "field:admin"], result.evidence_refs)

    def test_signatory_mismatch(self) -> None:
        result = compare_signatory_to_administrator([
            field("signed", "signed_by", "Ioana Pop", "application"),
            field("admin", "director", {"name": "Andrei Mureșan"}, "onrc"),
        ], rule_id="R04")
        self.assertEqual("mismatch", result.status)

    def test_demo02_turnover_mismatch(self) -> None:
        registry = tool(data={
            "cui": "41738200",
            "financials": {"2024": {"turnover": 8_100_000, "currency": "RON"}},
        })

        result = compare_pdf_turnover_to_registry(demo02_fields(), [registry], year=2024)

        self.assertEqual("R03", result.rule_id)
        self.assertEqual("turnover_2024_pdf_vs_registry", result.check_id)
        self.assertEqual("mismatch", result.status)
        self.assertEqual(12_400_000, result.left_value)
        self.assertEqual(8_100_000, result.right_value)
        self.assertEqual(4_300_000, result.difference)
        self.assertEqual("RON", result.currency)
        self.assertEqual(2024, result.year)
        self.assertIn("field:f-turnover", result.evidence_refs)
        self.assertIn("tool:anaf-fin-1", result.evidence_refs)
        json.dumps(result.to_dict(), ensure_ascii=False)

    def test_equal_turnover_matches_with_zero_difference(self) -> None:
        registry = tool(data={
            "cui": "41738200", "year": 2024,
            "turnover": "12.400.000 lei", "currency": "RON",
        })
        result = compare_pdf_turnover_to_registry(demo02_fields(), [registry], year=2024)
        self.assertEqual("match", result.status)
        self.assertEqual(0, result.difference)

    def test_registry_unavailable_is_unknown(self) -> None:
        result = compare_pdf_turnover_to_registry(
            demo02_fields(), [tool(status="unavailable")], year=2024
        )
        self.assertEqual("unknown", result.status)
        self.assertIsNone(result.right_value)

    def test_missing_pdf_year_is_unknown(self) -> None:
        fields = [field("f-turnover", "turnover", 12_400_000, "bilant")]
        registry = tool(data={"cui": "41738200", "year": 2024, "turnover": 8_100_000})
        result = compare_pdf_turnover_to_registry(fields, [registry], year=2024)
        self.assertEqual("unknown", result.status)

    def test_wrong_pdf_year_is_unknown(self) -> None:
        fields = demo02_fields()
        registry = tool(data={"cui": "41738200", "year": 2023, "turnover": 8_100_000})
        result = compare_pdf_turnover_to_registry(fields, [registry], year=2024)
        self.assertEqual("unknown", result.status)

    def test_company_cui_mismatch_makes_financial_comparison_unknown(self) -> None:
        registry = tool(data={
            "cui": "99999999", "year": 2024, "turnover": 8_100_000, "currency": "RON"
        })
        result = compare_pdf_turnover_to_registry(demo02_fields(), [registry], year=2024)
        self.assertEqual("unknown", result.status)
        self.assertIn("CUI", result.explanation)

    def test_currency_mismatch_is_unknown_without_conversion(self) -> None:
        registry = tool(data={
            "cui": "41738200", "year": 2024, "turnover": 8_100_000, "currency": "EUR"
        })
        result = compare_pdf_turnover_to_registry(demo02_fields(), [registry], year=2024)
        self.assertEqual("unknown", result.status)
        self.assertIn("Moneda", result.explanation)

    def test_missing_registry_currency_is_unknown(self) -> None:
        registry = tool(data={"cui": "41738200", "year": 2024, "turnover": 8_100_000})
        result = compare_pdf_turnover_to_registry(demo02_fields(), [registry], year=2024)
        self.assertEqual("unknown", result.status)

    def test_conflicting_registry_values_are_unknown(self) -> None:
        tools = [
            tool("t1", data={"cui": "41738200", "year": 2024, "turnover": 8_100_000}),
            tool("t2", data={"cui": "41738200", "year": 2024, "turnover": 8_200_000}),
        ]
        result = compare_pdf_turnover_to_registry(demo02_fields(), tools, year=2024)
        self.assertEqual("unknown", result.status)

    def test_other_annual_financial_value_uses_caller_rule_id(self) -> None:
        fields = [
            field("cui", "cui", "41738200", "bilant"),
            field("year", "fiscal_year", 2024, "bilant"),
            field("profit", "net_profit", 462_000, "bilant"),
        ]
        registry = tool(data={
            "cui": "41738200", "year": 2024, "net_profit": 462_000, "currency": "RON"
        })
        result = compare_pdf_financial_to_registry(
            fields, [registry], field_name="net_profit", year=2024, rule_id="R09"
        )
        self.assertEqual("R09", result.rule_id)
        self.assertEqual("match", result.status)


if __name__ == "__main__":
    unittest.main()
