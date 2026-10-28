"""Rules that consume Role 3's comparisons: R02, R03, R04, R10, R11."""
import dataclasses

import pytest

from rules_factories import VALID_CUI, clean, cmp, demo02, field_of, fld, run, tool_of


def swap(inputs, rule_id, *new):
    inputs["comparisons"] = [c for c in inputs["comparisons"] if c["rule_id"] != rule_id] + list(new)
    return inputs


def mismatch_for(rule_id):
    """A mismatching comparison for each rule, with real evidence from clean()."""
    return {
        "R02": cmp("name:AGRO", "R02", "mismatch", "AGRO NORD TRANS SRL", "field:f-name",
                   "AGRO NORD SRL", "tool:t-onrc"),
        "R03": cmp("turnover:2024:41738200", "R03", "mismatch", 12400000, "field:f-turn", 8100000, "tool:t-fin", 4300000),
        "R04": cmp("net_profit:2024:41738200", "R04", "mismatch", 520000, "field:f-np", 462000, "tool:t-fin", 58000),
        "R10": cmp("directors", "R10", "mismatch", [{"name": "Andrei Mureșan"}], "field:f-dir",
                   [{"name": "Ion Popa"}], "tool:t-onrc"),
        "R11": cmp("ubo", "R11", "mismatch", [{"name": "Andrei Mureșan"}], "field:f-ubo",
                   [{"name": "Ion Popa"}], "tool:t-onrc"),
    }[rule_id]


RULES = ["R02", "R03", "R04", "R10", "R11"]


@pytest.mark.parametrize("rule_id", RULES)
def test_pass_fail_unknown(rule_id):
    assert run(clean())[rule_id].result == "pass"

    failing = run(swap(clean(), rule_id, mismatch_for(rule_id)))[rule_id]
    assert failing.result == "fail" and failing.severity in ("red", "amber")
    assert len(failing.evidence) == 2

    missing = run(swap(clean(), rule_id))[rule_id]
    assert missing.result == "unknown" and missing.evidence == []


@pytest.mark.parametrize("rule_id", RULES)
def test_unknown_comparison_is_unknown(rule_id):
    unknown = dict(mismatch_for(rule_id), status="unknown", difference=None)
    assert run(swap(clean(), rule_id, unknown))[rule_id].result == "unknown"


@pytest.mark.parametrize("rule_id", RULES)
def test_unresolvable_evidence_never_passes_or_fails(rule_id):
    for status in ("match", "mismatch"):
        bad = dict(mismatch_for(rule_id), status=status)
        bad["right"] = {"value": bad["right"]["value"], "evidence": "tool:does-not-exist"}
        assert run(swap(clean(), rule_id, bad))[rule_id].result == "unknown"
        bad["right"] = {"value": bad["right"]["value"], "evidence": None}
        assert run(swap(clean(), rule_id, bad))[rule_id].result == "unknown"


@pytest.mark.parametrize("rule_id", RULES)
def test_comparison_backed_by_an_unverified_field_is_unknown(rule_id):
    inputs = swap(clean(), rule_id, mismatch_for(rule_id))
    ref = inputs["comparisons"][-1]["left"]["evidence"].split(":", 1)[1]
    field_of(inputs, ref).verified = False
    assert run(inputs)[rule_id].result == "unknown"


@pytest.mark.parametrize("rule_id, tool_id", [("R03", "t-fin"), ("R04", "t-fin"), ("R10", "t-onrc"), ("R11", "t-onrc")])
@pytest.mark.parametrize("status, message", [
    ("unavailable", "registru indisponibil, verificare manuală"),
    ("not_found", "nu există date în registru"),
])
def test_registry_not_ok_is_unknown_with_reason(rule_id, tool_id, status, message):
    inputs = swap(clean(), rule_id, mismatch_for(rule_id))       # even a mismatch cannot stand on a dead source
    tool = tool_of(inputs, tool_id)
    tool.status, tool.data = status, None
    finding = run(inputs)[rule_id]
    assert finding.result == "unknown" and message in finding.explanation


# ----------------------------------------------------------------- R03 specifics

def test_r03_fail_text_and_evidence():
    r03 = run(demo02())["R03"]
    assert r03.result == "fail" and r03.severity == "red"
    assert r03.evidence == ["field:f-turn", "tool:t-fin"]
    assert r03.explanation == (
        "Cifra de afaceri 2024: bilanț (bil-1) indică 12.400.000 RON, iar registrul ANAF (simulat) "
        "indică 8.100.000 RON; diferență 4.300.000 RON."
    )


def test_r03_mismatch_for_a_different_year_is_unknown():
    inputs = swap(clean(), "R03", cmp("turnover:2023:41738200", "R03", "mismatch", 12400000, "field:f-turn",
                                      8100000, "tool:t-fin", 4300000))
    out = run(inputs)["R03"]
    assert out.result == "unknown" and "an diferit" in out.explanation


def test_r03_registry_year_differs_from_the_bilant_year():
    inputs = clean()
    tool_of(inputs, "t-fin").args = {"cui": VALID_CUI, "year": 2023}
    tool_of(inputs, "t-fin").data["year"] = 2023
    out = run(inputs)["R03"]
    assert out.result == "unknown" and "an diferit" in out.explanation
    assert "2024" in out.explanation and "2023" in out.explanation


def test_r03_unknown_bilant_year_is_not_assumed():
    inputs = clean()
    inputs["fields"] = [f for f in inputs["fields"] if f.name != "fiscal_year"]
    swap(inputs, "R03", cmp("turnover", "R03", "match", 12400000, "field:f-turn", 12400000, "tool:t-fin", 0))
    assert run(inputs)["R03"].result == "unknown"


def test_r03_currency_must_match():
    inputs = clean()
    tool_of(inputs, "t-fin").data["currency"] = "EUR"
    out = run(inputs)["R03"]
    assert out.result == "unknown" and "monedă diferită" in out.explanation


def test_r03_tolerance_comes_from_yaml_and_zero_means_exact():
    inputs = swap(clean(), "R03", cmp("turnover:2024:41738200", "R03", "mismatch", 12400000, "field:f-turn",
                                      12399999, "tool:t-fin", 1))
    assert run(inputs)["R03"].result == "fail"                   # tolerance_abs 0: one leu is a mismatch


def test_r03_comparison_that_contradicts_the_field_is_not_trusted():
    inputs = swap(clean(), "R03", cmp("turnover:2024:41738200", "R03", "match", 8100000, "field:f-turn",
                                      8100000, "tool:t-fin", 0))
    assert run(inputs)["R03"].result == "unknown"                # field holds 12.400.000; engine reads it, never fixes it


def test_a_fail_beats_an_unknown_and_a_second_unknown_never_hides_it():
    inputs = demo02()
    inputs["comparisons"].append(cmp("turnover:2023:41738203", "R03", "unknown", None, None, None, None))
    assert run(inputs)["R03"].result == "fail"


def test_comparison_objects_are_accepted_as_well_as_dicts():
    @dataclasses.dataclass
    class Side:
        value: object
        evidence: str | None

    @dataclasses.dataclass
    class Comparison:
        check_id: str
        rule_id: str | None
        status: str
        left: Side
        right: Side
        difference: object
        explanation: str

    typed = [Comparison("turnover:2024:41738203", "R03", "mismatch", Side(12400000, "field:f-turn"),
                        Side(8100000, "tool:t-fin"), 4300000, "x")]
    inputs = demo02()
    inputs["comparisons"] = typed
    assert run(inputs)["R03"].result == "fail"


# ----------------------------------------------------------------- R02 severity

def test_r02_cui_mismatch_is_red_other_mismatches_amber():
    name = run(swap(clean(), "R02", mismatch_for("R02")))["R02"]
    assert (name.result, name.severity) == ("fail", "amber")

    cui = cmp(f"cui:{VALID_CUI}", "R02", "mismatch", VALID_CUI, "field:f-cui", "18189442", "field:f-cui-app")
    inputs = swap(clean(), "R02", mismatch_for("R02"), cui)
    field_of(inputs, "f-cui-app").value = "18189442"
    both = run(inputs)["R02"]
    assert (both.result, both.severity) == ("fail", "red")
    inputs = swap(clean(), "R02", cui)
    field_of(inputs, "f-cui-app").value = "18189442"
    assert run(inputs)["R02"].severity == "red"


def test_r02_identity_comparison_without_rule_id_is_not_consumed():
    unmapped = cmp("cui:x", None, "mismatch", VALID_CUI, "field:f-cui", "1", "field:f-cui-app")
    out = run(swap(clean(), "R02", unmapped))["R02"]
    assert out.result == "unknown"


def test_r04_and_r10_r11_pass_text_names_both_sources():
    out = run(clean())
    assert "registrul ANAF (simulat)" in out["R04"].explanation and "520.000 RON" in out["R04"].explanation
    assert "registrul ONRC (simulat)" in out["R10"].explanation
