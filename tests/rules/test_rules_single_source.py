"""Rules that read fields, one registry result or the document list: R01, R05-R09, R12, R14, R15."""
import pytest

from rules_factories import VALID_CUI, clean, doc, drop_fields, field_of, fld, run, tool_of


# ----------------------------------------------------------------- R01

def test_r01_pass_fail_unknown():
    assert run(clean())["R01"].result == "pass"

    inputs = clean()
    field_of(inputs, "f-cui").value = "41738203"
    r01 = run(inputs)["R01"]
    assert r01.result == "fail" and r01.severity == "red"
    assert r01.evidence == ["field:f-cui"] and "ar trebui să fie 0, nu 3" in r01.explanation

    out = run(drop_fields(clean(), "f-cui", "f-cui-app"))["R01"]
    assert out.result == "unknown" and out.evidence == []


@pytest.mark.parametrize("cui", ["18189442", "14399840", "RO41738200", "41738200"])
def test_r01_known_valid_cuis(cui):
    inputs = clean()
    field_of(inputs, "f-cui").value = cui
    assert run(inputs)["R01"].result == "pass"


@pytest.mark.parametrize("cui", ["18189443", "1", "12345678901"])
def test_r01_invalid_cuis(cui):
    inputs = clean()
    field_of(inputs, "f-cui").value = cui
    assert run(inputs)["R01"].result == "fail"


def test_r01_unverified_or_nonnumeric_never_passes():
    inputs = clean()
    for f in inputs["fields"]:
        f.verified = False if f.name == "cui" else f.verified
    assert run(inputs)["R01"].result == "unknown"
    inputs = drop_fields(clean(), "f-cui-app")
    field_of(inputs, "f-cui").value = "abc"
    assert run(inputs)["R01"].result == "unknown"


# ----------------------------------------------------------------- R05

def test_r05_pass_fail_unknown():
    assert run(clean())["R05"].result == "pass"

    inputs = clean()
    field_of(inputs, "f-li").value = 4500001
    r05 = run(inputs)["R05"]
    assert (r05.result, r05.severity) == ("fail", "amber")
    assert set(r05.evidence) == {"field:f-ta", "field:f-eq", "field:f-li"}
    assert "1 RON" in r05.explanation and "7.300.000 RON" in r05.explanation

    assert run(drop_fields(clean(), "f-eq"))["R05"].result == "unknown"


def test_r05_unverified_conflicting_and_mixed_documents_are_unknown():
    inputs = clean()
    field_of(inputs, "f-eq").verified = False
    assert run(inputs)["R05"].result == "unknown"

    inputs = clean()
    inputs["fields"].append(fld("f-ta2", "total_assets", 9999999))
    assert run(inputs)["R05"].result == "unknown"

    inputs = clean()
    field_of(inputs, "f-eq").doc_id = "other-doc"             # values from different documents
    assert run(inputs)["R05"].result == "unknown"


# ----------------------------------------------------------------- R06

def test_r06_pass_fail_unknown():
    assert run(clean())["R06"].result == "pass"

    inputs = clean()
    tool_of(inputs, "t-co").data["active"] = False
    r06 = run(inputs)["R06"]
    assert (r06.result, r06.severity, r06.evidence) == ("fail", "red", ["tool:t-co"])

    inputs = clean()
    co = tool_of(inputs, "t-co")
    co.status, co.data = "unavailable", None
    assert "registru indisponibil, verificare manuală" in run(inputs)["R06"].explanation

    inputs = clean()
    co = tool_of(inputs, "t-co")
    co.status, co.data = "not_found", None
    r06 = run(inputs)["R06"]
    assert r06.result == "unknown" and "nu există date în registru" in r06.explanation

    inputs = clean()
    tool_of(inputs, "t-co").data.pop("active")
    assert run(inputs)["R06"].result == "unknown"


def test_r06_registry_for_another_cui_is_not_used():
    inputs = clean()
    tool_of(inputs, "t-co").args = {"cui": "18189442"}
    assert run(inputs)["R06"].result == "unknown"


# ----------------------------------------------------------------- R07

def test_r07_pass_fail_unknown():
    assert run(clean())["R07"].result == "pass"

    inputs = clean()
    tool_of(inputs, "t-co").data["vat_cancelled"] = "2026-06-01"
    r07 = run(inputs)["R07"]
    assert r07.result == "fail" and "01.06.2026" in r07.explanation and "14.10.2026" in r07.explanation

    inputs = clean()
    tool_of(inputs, "t-co").data["vat_cancelled"] = "2022-01-01"
    assert run(inputs)["R07"].result == "pass"

    inputs = clean()
    tool_of(inputs, "t-co").data["vat_since"] = "2026-03-01"       # registered recently, no cancellation date
    assert run(inputs)["R07"].result == "unknown"

    assert run(drop_fields(clean(), "f-appdate"))["R07"].result == "unknown"


# ----------------------------------------------------------------- R08

def test_r08_pass_fail_unknown():
    assert run(clean())["R08"].result == "pass"

    inputs = clean()
    field_of(inputs, "f-cafdate").value = "2026-08-01"
    r08 = run(inputs)["R08"]
    assert (r08.result, r08.severity) == ("fail", "amber")
    assert "01.08.2026" in r08.explanation and "74 zile" in r08.explanation

    assert run(drop_fields(clean(), "f-cafdate"))["R08"].result == "unknown"

    inputs = clean()
    field_of(inputs, "f-cafdate").value = "2026-11-01"             # issued after the application
    assert run(inputs)["R08"].result == "unknown"


def test_r08_uses_the_application_date_not_the_system_clock():
    inputs = clean()
    field_of(inputs, "f-appdate").value = "2020-01-15"
    field_of(inputs, "f-cafdate").value = "2020-01-02"
    assert run(inputs)["R08"].result == "pass"                     # years before today's date

    field_of(inputs, "f-cafdate").value = "2019-11-01"
    assert run(inputs)["R08"].result == "fail"

    field_of(inputs, "f-appdate").value = "2099-12-31"
    field_of(inputs, "f-cafdate").value = "2099-12-20"
    assert run(inputs)["R08"].result == "pass"                     # a date after today's date


# ----------------------------------------------------------------- R09

def test_r09_pass_fail_unknown():
    assert run(clean())["R09"].result == "pass"

    inputs = clean()
    field_of(inputs, "f-cafdebts").value = True
    inputs["fields"].append(fld("f-cafdebt", "caf_total_debt", 125000, doc_id="caf-1"))
    r09 = run(inputs)["R09"]
    assert (r09.result, r09.severity) == ("fail", "red")
    assert "125.000 RON" in r09.explanation and "field:f-cafdebts" in r09.evidence

    assert run(drop_fields(clean(), "f-cafdebts"))["R09"].result == "unknown"

    inputs = clean()
    field_of(inputs, "f-cafdebts").verified = False
    assert run(inputs)["R09"].result == "unknown"


def test_r09_contradictory_debt_data_is_unknown():
    inputs = clean()
    inputs["fields"].append(fld("f-cafdebt", "caf_total_debt", 125000, doc_id="caf-1"))
    assert run(inputs)["R09"].result == "unknown"                  # says no debts, but a debt amount
    inputs = clean()
    inputs["fields"].append(fld("f-cafdebts2", "caf_has_debts", True, doc_id="caf-2"))
    assert run(inputs)["R09"].result == "unknown"                  # two documents disagree


# ----------------------------------------------------------------- R14

def test_r14_pass_fail_unknown():
    assert run(clean())["R14"].result == "pass"

    inputs = clean()
    inputs["documents"] = [d for d in inputs["documents"] if d.type != "caf"]
    r14 = run(inputs)["R14"]
    assert (r14.result, r14.severity) == ("fail", "amber")
    assert "caf" in r14.explanation and r14.evidence

    inputs = clean()
    inputs["documents"].append(doc("scan-1", "unknown", readable=False))
    r14 = run(inputs)["R14"]
    assert r14.result == "fail" and r14.evidence == ["doc:scan-1"] and "scan-1.pdf" in r14.explanation

    out = run(clean(), documents=None)["R14"]
    assert out.result == "unknown" and out.evidence == []
    assert run(clean(), documents=[])["R14"].result == "unknown"


# ----------------------------------------------------------------- deferred

@pytest.mark.parametrize("rule_id, reason", [("R12", "sursă de sancțiuni neintegrată"), ("R15", "indicator de injecție")])
def test_deferred_rules_are_unknown_never_pass(rule_id, reason):
    for inputs in (clean(), {"fields": [], "tools": [], "comparisons": [], "documents": []}):
        finding = run(inputs)[rule_id]
        assert finding.result == "unknown" and finding.evidence == []
        assert finding.explanation.startswith("Neimplementat în Sprint 2:") and reason in finding.explanation
        assert finding.severity == "red"                           # severity from rules.yaml
