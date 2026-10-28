"""R13: open insolvency / enforcement from court_cases, with no score."""
import pytest

from rules_factories import ENFORCEMENT_CASE, VALID_CUI, clean, demo02, drop_fields, field_of, run, tool_of


def with_cases(*cases, inputs=None):
    inputs = inputs or clean()
    tool_of(inputs, "t-court").data["cases"] = [dict(c) for c in cases]
    return inputs


def case(**changes):
    return {**ENFORCEMENT_CASE, **changes}


INSOLVENCY = case(number="77/3/2026", subject="procedura insolvenței", category="insolvency", court="Tribunalul București")


def test_no_cases_passes_when_the_tool_is_ok():
    out = run(clean())["R13"]
    assert out.result == "pass" and out.evidence == ["tool:t-court"]
    assert "portalul instanțelor (simulat)".capitalize() in out.explanation


def test_open_enforcement_as_debtor_is_amber_fail():
    out = run(with_cases(ENFORCEMENT_CASE))["R13"]
    assert (out.result, out.severity) == ("fail", "amber")
    assert "2318/117/2025" in out.explanation and "Tribunalul Cluj" in out.explanation


def test_open_insolvency_as_debtor_is_red_fail():
    out = run(with_cases(INSOLVENCY))["R13"]
    assert (out.result, out.severity) == ("fail", "red")
    assert "77/3/2026" in out.explanation and "insolvență" in out.explanation


def test_insolvency_outranks_enforcement_and_lists_both_cases():
    out = run(with_cases(ENFORCEMENT_CASE, INSOLVENCY))["R13"]
    assert out.severity == "red"
    assert "77/3/2026" in out.explanation and "2318/117/2025" in out.explanation


def test_closed_case_passes():
    assert run(with_cases(case(status="closed")))["R13"].result == "pass"
    assert run(with_cases(case(status="închis")))["R13"].result == "pass"


@pytest.mark.parametrize("role", ["creditor", "reclamant", "plangator"])
def test_case_as_creditor_or_plaintiff_passes(role):
    assert run(with_cases(case(party_role=role)))["R13"].result == "pass"


def test_other_categories_do_not_count():
    commercial = case(subject="litigiu comercial", category="commercial")
    assert run(with_cases(commercial))["R13"].result == "pass"


def test_possible_name_match_is_unknown_with_the_case_number():
    other_form = case(party_name="AGRO NORD TRANS S.A.")
    out = run(with_cases(other_form))["R13"]
    assert out.result == "unknown" and "posibilă potrivire, verificare analist" in out.explanation
    assert "2318/117/2025" in out.explanation and "formă juridică diferită" in out.explanation

    similar = case(party_name="AGRO NORD TRANSPORT SRL")
    out = run(with_cases(similar))["R13"]
    assert out.result == "unknown" and "denumire asemănătoare" in out.explanation


def test_exact_name_and_legal_form_is_certain_even_without_cui():
    same = case(party_name="Agro Nord Trans S.R.L.")
    assert run(with_cases(same))["R13"].result == "fail"


def test_same_name_in_a_different_city_is_uncertain():
    inputs = with_cases(case(party_name="AGRO NORD TRANS SRL", party_city="Timișoara"))
    inputs["fields"].append(__import__("rules_factories").fld("f-addr", "address", "Str. Fabricii 7, Cluj-Napoca"))
    out = run(inputs)["R13"]
    assert out.result == "unknown" and "oraș diferit" in out.explanation


def test_case_of_another_company_is_ignored():
    assert run(with_cases(case(cui="18189442")))["R13"].result == "pass"
    assert run(with_cases(case(party_name="CU TOTUL ALTA FIRMA SRL")))["R13"].result == "pass"


def test_case_with_matching_cui_is_certain():
    assert run(with_cases(case(cui=VALID_CUI)))["R13"].result == "fail"


def test_uncertain_case_does_not_hide_a_certain_one():
    inputs = with_cases(ENFORCEMENT_CASE, case(number="9/9/2026", party_name="AGRO NORD TRANS SA"))
    out = run(inputs)["R13"]
    assert out.result == "fail" and "9/9/2026" in out.explanation


def test_unclear_status_or_role_is_unknown():
    assert run(with_cases(case(status="suspendat")))["R13"].result == "unknown"
    assert run(with_cases(case(party_role="")))["R13"].result == "unknown"


@pytest.mark.parametrize("status, message", [
    ("unavailable", "portal instanțe indisponibil / date lipsă"),
    ("not_found", "nu există date în registru"),
])
def test_tool_not_ok_is_unknown(status, message):
    inputs = clean()
    court = tool_of(inputs, "t-court")
    court.status, court.data = status, None
    out = run(inputs)["R13"]
    assert out.result == "unknown" and message in out.explanation and out.evidence == []


def test_missing_tool_is_unknown():
    inputs = clean()
    inputs["tools"] = [t for t in inputs["tools"] if t.tool != "court_cases"]
    assert run(inputs)["R13"].result == "unknown"


def test_court_results_for_another_cui_are_not_used():
    inputs = with_cases(ENFORCEMENT_CASE)
    tool_of(inputs, "t-court").args = {"cui": "18189442"}
    assert run(inputs)["R13"].result == "unknown"


def test_malformed_case_list_is_unknown():
    inputs = clean()
    tool_of(inputs, "t-court").data = {"cui": VALID_CUI, "oops": 1}
    assert run(inputs)["R13"].result == "unknown"


def test_no_score_in_any_r13_text():
    for inputs in (clean(), demo02(), with_cases(INSOLVENCY)):
        text = run(inputs)["R13"].explanation.lower()
        assert "scor" not in text and "/100" not in text and "puncte" not in text


def test_registry_flags_in_the_tool_data_are_not_trusted():
    inputs = clean()
    tool_of(inputs, "t-court").data.update(has_open_enforcement=True, has_open_insolvency=True, open_cases_count=3)
    assert run(inputs)["R13"].result == "pass"                   # the engine reads the cases, not summaries
