"""Engine-level behaviour: shape, determinism, scenarios, config validation, guards."""
import copy
import re
from pathlib import Path

import pytest
import yaml

from app.models import Finding
from app.rules import RulesConfigError, evaluate_rules, rule_catalog
from app.rules.config import DEFAULT_CONFIG_PATH
from rules_factories import (
    DEMO02_CUI, VALID_CUI, clean, demo02, drop_fields, field_of, run, tool_of,
)

RULES_DIR = Path(__file__).resolve().parents[2] / "app" / "rules"
IMPLEMENTED = ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09", "R10", "R11", "R13", "R14"]
DEFERRED = ["R12", "R15"]


def findings_of(inputs, case_id="DEMO-02"):
    return evaluate_rules(case_id, inputs["fields"], inputs["tools"], inputs["comparisons"], inputs["documents"])


def test_exactly_fifteen_sorted_stable_findings():
    inputs = demo02()
    first = findings_of(inputs)
    assert [f.rule_id for f in first] == [f"R{i:02d}" for i in range(1, 16)]
    assert [f.id for f in first] == [f"finding-R{i:02d}-DEMO-02" for i in range(1, 16)]
    assert first == findings_of(inputs)                       # same input, same output
    assert [f.model_dump() for f in first] == [f.model_dump() for f in findings_of(demo02())]


def test_findings_validate_against_the_real_model():
    for finding in findings_of(demo02()):
        assert isinstance(finding, Finding)
        assert Finding.model_validate(finding.model_dump()) == finding
        assert finding.checker == "n/a"


@pytest.mark.parametrize("make", [clean, demo02])
def test_every_evidence_ref_exists_in_the_inputs(make):
    inputs = make()
    known = ({f"field:{f.id}" for f in inputs["fields"]} | {f"tool:{t.id}" for t in inputs["tools"]}
             | {f"doc:{d.id}" for d in inputs["documents"]})
    for finding in findings_of(inputs):
        assert set(finding.evidence) <= known, finding.rule_id
        if finding.result in ("pass", "fail"):
            assert finding.evidence, f"{finding.rule_id} is {finding.result} without evidence"


def test_demo02_end_to_end():
    out = run(demo02())
    r03 = out["R03"]
    assert (r03.result, r03.severity) == ("fail", "red")
    assert set(r03.evidence) == {"field:f-turn", "tool:t-fin"}
    for text in ("4.300.000 RON", "12.400.000", "8.100.000", "simulat"):
        assert text in r03.explanation
    r13 = out["R13"]
    assert (r13.result, r13.severity) == ("fail", "amber")
    assert "2318/117/2025" in r13.explanation and "Tribunalul Cluj" in r13.explanation
    assert "LEASING FICTIV IFN SA" in r13.explanation
    assert not re.search(r"\b\d+\s*/\s*100\b|scor", r13.explanation.lower())   # no litigation score
    assert r13.evidence == ["tool:t-court"]


def test_demo02_cui_from_the_spec_fails_its_check_digit():
    """41738203 is NOT a valid CUI: 753217532 requires control digit 0 for 4173820, not 3.
    The engine reports what the algorithm says. Role 1 must use a valid CUI (e.g. 41738200)
    or the lead must rule on R01; the engine is not bent to make the demo pass."""
    out = run(demo02())
    assert out["R01"].result == "fail" and out["R01"].severity == "red"
    assert "41738203" in out["R01"].explanation and "cifră de control" in out["R01"].explanation
    body = DEMO02_CUI[:-1].zfill(9)
    total = sum(int(d) * w for d, w in zip(body, (7, 5, 3, 2, 1, 7, 5, 3, 2)))
    assert (total * 10 % 11) % 10 == 0 and DEMO02_CUI[-1] == "3"
    assert run(clean())["R01"].result == "pass"                # same company, valid CUI


def test_clean_scenario_all_implemented_pass_deferred_unknown():
    out = run(clean(), case_id="C-OK")
    for rule_id in IMPLEMENTED:
        assert out[rule_id].result == "pass", (rule_id, out[rule_id].explanation)
    for rule_id in DEFERRED:
        assert out[rule_id].result == "unknown"
        assert out[rule_id].explanation.startswith("Neimplementat în Sprint 2:")


def test_incomplete_scenario_registry_unavailable_is_unknown_not_pass():
    inputs = clean()
    fin = tool_of(inputs, "t-fin")
    fin.status, fin.data = "unavailable", None
    out = run(inputs)
    assert out["R03"].result == "unknown" and out["R04"].result == "unknown"
    assert "registru indisponibil, verificare manuală" in out["R03"].explanation
    assert out["R03"].severity == "amber"                      # unknown_severity from rules.yaml
    assert out["R01"].result == "pass"


def test_unverified_field_is_ignored():
    inputs = clean()
    field_of(inputs, "f-turn").verified = False
    assert run(inputs)["R03"].result == "unknown"


def test_nothing_passes_on_an_empty_case():
    out = run({"fields": [], "tools": [], "comparisons": [], "documents": []})
    assert {f.result for f in out.values()} == {"unknown"}
    out = evaluate_rules("EMPTY", [], [], [])
    assert len(out) == 15 and {f.result for f in out} == {"unknown"}


def test_does_not_mutate_inputs():
    inputs = demo02()
    before = copy.deepcopy([[f.model_dump() for f in inputs["fields"]], [t.model_dump() for t in inputs["tools"]],
                            inputs["comparisons"]])
    findings_of(inputs)
    after = [[f.model_dump() for f in inputs["fields"]], [t.model_dump() for t in inputs["tools"]],
             inputs["comparisons"]]
    assert before == after


def test_a_broken_rule_input_degrades_to_unknown():
    inputs = clean()
    inputs["comparisons"].append({"rule_id": "R03", "status": "mismatch", "left": "garbage", "right": 5})
    out = run(inputs)
    assert out["R03"].result in ("unknown", "pass") and out["R03"].result != "fail"


# ------------------------------------------------------------------ catalog


def test_rule_catalog_has_all_rules_and_flags_deferred():
    catalog = rule_catalog()
    assert [c["rule_id"] for c in catalog] == [f"R{i:02d}" for i in range(1, 16)]
    for entry in catalog:
        assert set(entry) == {"rule_id", "description", "severity", "implemented", "mandatory",
                              "inputs", "thresholds"}
    by_id = {c["rule_id"]: c for c in catalog}
    assert [r for r, c in by_id.items() if not c["implemented"]] == DEFERRED
    assert by_id["R03"]["thresholds"]["tolerance_abs"] == {
        "value": 0, "source": "team doc rule catalogue", "confirmed": False}
    for entry in catalog:
        for threshold in entry["thresholds"].values():
            assert threshold["source"] and threshold["confirmed"] is False


# ------------------------------------------------------------------ rules.yaml validation


def write_variant(tmp_path, mutate):
    data = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["rules"].pop("R07"), "missing rules"),
    (lambda d: d["rules"]["R03"].update(severity="purple"), "severity"),
    (lambda d: d["rules"]["R03"].update(surprise=1), "unknown keys"),
    (lambda d: d.update(extra=1), "unknown top-level"),
    (lambda d: d["rules"]["R03"]["thresholds"].pop("tolerance_abs"), "missing thresholds"),
    (lambda d: d["rules"]["R03"]["thresholds"]["tolerance_abs"].pop("source"), "value, source, confirmed"),
    (lambda d: d["rules"]["R03"]["thresholds"]["tolerance_abs"].update(confirmed="yes"), "confirmed"),
    (lambda d: d["rules"]["R12"].pop("deferred_reason_ro"), "deferred_reason_ro"),
    (lambda d: d["rules"].update(R16=copy.deepcopy(d["rules"]["R01"])), "unknown rule ids"),
    (lambda d: d["defaults"].update(unknown_severity="x"), "unknown_severity"),
])
def test_bad_rules_yaml_raises_a_clear_error(tmp_path, mutate, message):
    path = write_variant(tmp_path, mutate)
    with pytest.raises(RulesConfigError, match=message):
        evaluate_rules("X", [], [], [], config_path=path)


def test_missing_rules_file_is_a_clear_error(tmp_path):
    with pytest.raises(RulesConfigError, match="cannot read"):
        evaluate_rules("X", [], [], [], config_path=str(tmp_path / "nope.yaml"))


def test_changing_a_threshold_in_yaml_changes_the_result(tmp_path):
    inputs = clean()
    field_of(inputs, "f-ta").value = 7300500                    # 500 off the balance
    assert run(inputs)["R05"].result == "fail"
    path = write_variant(tmp_path, lambda d: d["rules"]["R05"]["thresholds"]["tolerance_abs"].update(value=1000))
    findings = evaluate_rules("X", inputs["fields"], inputs["tools"], inputs["comparisons"],
                              inputs["documents"], config_path=path)
    assert {f.rule_id: f for f in findings}["R05"].result == "pass"


# ------------------------------------------------------------------ guards


def test_rules_folder_never_touches_ground_truth_or_models():
    forbidden = ["planted_errors", "expected", "ground_truth", "companies.json", "app.llm",
                 "anthropic", "openai", "import requests", "urllib", "datetime.now", "date.today", "time.time"]
    offenders = []
    for path in RULES_DIR.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".yaml", ".md"}:
            text = path.read_text(encoding="utf-8").lower()
            offenders += [(path.name, word) for word in forbidden if word in text]
    assert offenders == []


def test_engine_has_no_file_writes():
    for path in RULES_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"open\([^)]*['\"][wa]", text), path.name
