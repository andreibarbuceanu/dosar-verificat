from decimal import Decimal

import pytest

from app.extraction import normalize as n


@pytest.mark.parametrize("raw, expected", [
    ("12.400.000", 12400000),
    ("12.400.000 lei", 12400000),
    ("RON 12.400.000", 12400000),
    ("12 400 000", 12400000),
    ("12 400 000", 12400000),
    ("12,400,000", 12400000),
    ("1.234,56", 1234.56),
    ("1,234.56", 1234.56),
    ("-123.000", -123000),
    ("−123.000", -123000),
    ("(123.000)", -123000),
    ("(123.000) lei", -123000),
    ("38", 38),
    ("33,33%", 33.33),
    ("50 %", 50),
    ("12.5", 12.5),
])
def test_parse_number(raw, expected):
    value = n.to_python(n.parse_number(raw))
    assert value == expected
    assert type(value) is type(expected)


@pytest.mark.parametrize("raw", ["", "abc", "12.40.000", "12.400 mii lei", "1.2.3", "cifra 12"])
def test_parse_number_refuses_to_guess(raw):
    assert n.parse_number(raw) is None


@pytest.mark.parametrize("raw", [
    "14.10.2026", "14/10/2026", "14-10-2026", "2026-10-14",
    "14 octombrie 2026", "14 Octombrie 2026", "14 oct. 2026",
])
def test_parse_date(raw):
    assert n.parse_date(raw) == "2026-10-14"


@pytest.mark.parametrize("raw", ["31.02.2024", "14 brumarie 2026", "2026", "data 14.10.2026"])
def test_parse_date_invalid(raw):
    assert n.parse_date(raw) is None


def test_numbers_in_quote_keep_sign():
    assert n.numbers_in("Pierdere netă (123.000) (98.000)") == {Decimal(-123000), Decimal(-98000)}
    assert Decimal(-123000) in n.numbers_in("Rezultat net: -123.000 lei")
    assert Decimal(2024) in n.numbers_in("Exercițiul 2023-2024")  # a range is not a minus


def test_numbers_in_space_grouped_columns():
    nums = n.numbers_in("Cifra de afaceri 12 400 000 9 750 000")
    assert {Decimal(12400000), Decimal(9750000)} <= nums


def test_codes_years_bools():
    assert n.parse_code("RO 41738203") == "41738203"
    assert n.parse_code("4941") == "4941"
    assert n.parse_code("J40/12/2020") is None
    assert n.parse_year("2024") == 2024
    assert n.parse_year("24") is None
    assert n.parse_bool("Da") is True and n.parse_bool("false") is False
    assert n.parse_bool("poate") is None


def test_norm_equates_cedilla_comma_spaces_quotes_dashes():
    assert n.norm("Bucureşti  „SRL” – ţară") == n.norm("BUCUREȘTI \"srl\" - țară")
    assert n.norm("cifra­de afaceri") == n.norm("cifrade afaceri")


def test_page_locate_returns_exact_page_text():
    page = n.Page("Sediul: Str. Gării nr.\n 7, Bucureşti")
    assert page.locate("Str. Gării nr. 7, București") == "Str. Gării nr.\n 7, Bucureşti"
    assert page.locate("Str. Morii") is None
    assert page.locate("   ") is None
