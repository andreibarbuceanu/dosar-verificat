from datetime import date, datetime
from decimal import Decimal
import unittest

from app.verification import (
    normalize_company_name,
    normalize_cui,
    normalize_currency,
    normalize_date,
    normalize_money,
    normalize_person_name,
    normalize_year,
)


class NormalizationTests(unittest.TestCase):
    def test_cui_accepts_ro_prefix_and_formatting(self) -> None:
        self.assertEqual("41738200", normalize_cui(" RO 41.738.200 "))

    def test_cui_rejects_non_numeric_and_bool(self) -> None:
        self.assertIsNone(normalize_cui("RO41A738200"))
        self.assertIsNone(normalize_cui(True))

    def test_company_name_normalizes_diacritics_punctuation_and_legal_form(self) -> None:
        self.assertEqual(
            normalize_company_name("Școala Nord S.R.L."),
            normalize_company_name("SCOALA NORD societate cu răspundere limitată"),
        )

    def test_person_name_tolerates_order_titles_and_diacritics(self) -> None:
        self.assertEqual(
            normalize_person_name("Dl. Andrei Mureșan"),
            normalize_person_name("MURESAN, ANDREI"),
        )

    def test_money_parses_romanian_and_international_formats(self) -> None:
        self.assertEqual(Decimal("12400000"), normalize_money("12.400.000 RON"))
        self.assertEqual(Decimal("1234.56"), normalize_money("1.234,56 lei"))
        self.assertEqual(Decimal("12400000"), normalize_money("12,400,000"))

    def test_money_handles_parenthesized_negative(self) -> None:
        self.assertEqual(Decimal("-1250"), normalize_money("(1.250 RON)"))

    def test_money_rejects_ambiguous_or_non_numeric_input(self) -> None:
        self.assertIsNone(normalize_money("aproximativ un milion"))
        self.assertIsNone(normalize_money(True))

    def test_currency_aliases(self) -> None:
        self.assertEqual("RON", normalize_currency("lei"))
        self.assertEqual("EUR", normalize_currency("euro"))
        self.assertIsNone(normalize_currency("GBP"))

    def test_year_range(self) -> None:
        self.assertEqual(2024, normalize_year("2024"))
        self.assertIsNone(normalize_year(24))
        self.assertIsNone(normalize_year(True))

    def test_dates(self) -> None:
        expected = date(2026, 10, 14)
        self.assertEqual(expected, normalize_date("2026-10-14"))
        self.assertEqual(expected, normalize_date("14.10.2026"))
        self.assertEqual(expected, normalize_date("14 octombrie 2026"))
        self.assertEqual(expected, normalize_date(datetime(2026, 10, 14, 9, 30)))
        self.assertIsNone(normalize_date("31.02.2026"))


if __name__ == "__main__":
    unittest.main()
