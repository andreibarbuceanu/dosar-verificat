"""
Shape checks for the synthetic registry fixtures (docs/SPRINT2_CONTRACT.md §3, v1.0).

Data only: no lookup, comparison or rule logic here (that is Roles 2-5).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from app.models import ToolResult

REGISTRY = Path(__file__).resolve().parents[2] / "fixtures" / "registry"
MANIFEST = REGISTRY / "cases_manifest.json"
MANIFEST_INCOMPLETE = REGISTRY / "cases_manifest.incomplete.json"

AS_OF = "2026-10-20T00:00:00+00:00"
SOURCE = "synthetic_fixture"
TOOLS = ["anaf_company", "anaf_financials", "onrc_company", "court_cases"]

# Exact key order of every payload; Role 2 serves them as-is inside ToolResult.data.
KEYS = {
    "anaf_company": ["source", "cui", "active", "vat_registered", "vat_since", "e_factura"],
    "anaf_financials": ["source", "cui", "year", "currency",
                        "turnover", "total_revenue", "total_expenses", "net_profit"],
    "onrc_company": ["source", "cui", "name", "reg_com", "status", "address", "directors"],
    "court_cases": ["source", "cui", "cases"],
}
ADDRESS_KEYS = ["street", "number", "city", "county", "postal_code"]
DIRECTOR_KEYS = ["name", "can_sign"]
COURT_CASE_KEYS = ["number", "court", "subject", "category", "party_role",
                   "other_party", "stage", "status", "registered"]
MONEY_KEYS = ["turnover", "total_revenue", "total_expenses", "net_profit"]

# Contract v1.0 defines no court vocabularies. Categories come from the Deduction
# comment in app/models.py; the other sets hold only the values the data uses.
CATEGORIES = {"insolvency", "enforcement", "anaf_plaintiff", "commercial"}
PARTY_ROLES = {"debitor"}
STAGES = {"executare"}
CASE_STATUSES = {"open"}

LEAK_STRINGS = ["expected", "planted_errors", "ground_truth", "pdf_value", "true_value"]
DEMO02_FORBIDDEN = ["12400000", "12.400.000", "4300000", "4.300.000"]


# ---------- helpers ----------

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cui_ok(cui: str) -> bool:
    """Romanian CUI check digit: key 753217532 over the body, left-padded to 9 digits."""
    if not re.fullmatch(r"[0-9]{2,10}", cui):
        return False
    body, control = cui[:-1].zfill(9), int(cui[-1])
    total = sum(int(d) * int(k) for d, k in zip(body, "753217532"))
    return total * 10 % 11 % 10 == control


def is_iso_date(value) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    date.fromisoformat(value)   # raises on 2025-02-30
    return True


def payloads(manifest_path: Path, case_id: str):
    """(tool, relative path, payload) for every payload of one case; financials hold one per year."""
    case = load(manifest_path)["cases"][case_id]
    for tool, rel in case["paths"].items():
        data = load(REGISTRY / rel)
        for payload in (data if tool == "anaf_financials" else [data]):
            yield tool, rel, payload


MANIFESTS = [MANIFEST, MANIFEST_INCOMPLETE]
CASES = [(m, case_id) for m in MANIFESTS for case_id in load(m)["cases"]]
CASE_IDS = [f"{m.stem}:{case_id}" for m, case_id in CASES]
JSON_FILES = sorted(REGISTRY.rglob("*.json"))


# ---------- files and manifests ----------

def test_registry_has_json_files():
    assert MANIFEST in JSON_FILES and MANIFEST_INCOMPLETE in JSON_FILES
    assert len(JSON_FILES) > 2


@pytest.mark.parametrize("path", JSON_FILES, ids=lambda p: p.relative_to(REGISTRY).as_posix())
def test_json_file_parses_and_is_canonical(path: Path):
    """UTF-8, 2-space indent, diacritics not escaped, LF line ends, trailing newline."""
    raw = path.read_bytes()
    obj = json.loads(raw.decode("utf-8"))
    assert raw == (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: p.name)
def test_manifest_shape(manifest_path: Path):
    manifest = load(manifest_path)
    assert list(manifest) == ["as_of", "cases"]
    assert manifest["as_of"] == AS_OF
    assert datetime.fromisoformat(manifest["as_of"]).tzinfo is not None
    assert manifest["cases"]

    for case_id, case in manifest["cases"].items():
        assert list(case) == ["cui", "paths"], case_id
        assert cui_ok(case["cui"]), f"{case_id}: CUI {case['cui']} fails the check digit"
        assert set(case["paths"]) <= set(TOOLS), case_id
        for rel in case["paths"].values():
            assert not Path(rel).is_absolute() and ".." not in Path(rel).parts, rel
            assert (REGISTRY / rel).is_file(), f"{case_id}: missing {rel}"


def test_default_manifest_cases():
    cases = load(MANIFEST)["cases"]
    assert {"DEMO-01", "DEMO-02"} <= set(cases)
    for case_id, case in cases.items():
        assert list(case["paths"]) == TOOLS, case_id
        assert case["paths"]["onrc_company"] == f"{case_id}/onrc.json"
    # Tools look up by CUI, so one CUI must lead to exactly one case.
    cuis = [case["cui"] for case in cases.values()]
    assert len(cuis) == len(set(cuis))


def test_incomplete_manifest():
    cases = load(MANIFEST_INCOMPLETE)["cases"]
    assert list(cases) == ["DEMO-01-INCOMPLETE"]
    incomplete = cases["DEMO-01-INCOMPLETE"]
    demo01 = load(MANIFEST)["cases"]["DEMO-01"]

    assert incomplete["cui"] == demo01["cui"]
    assert "anaf_financials" not in incomplete["paths"]
    assert incomplete["paths"] == {k: v for k, v in demo01["paths"].items() if k != "anaf_financials"}


# ---------- payloads ----------

@pytest.mark.parametrize("manifest_path, case_id", CASES, ids=CASE_IDS)
def test_payload_cui_matches_manifest(manifest_path: Path, case_id: str):
    cui = load(manifest_path)["cases"][case_id]["cui"]
    for tool, rel, payload in payloads(manifest_path, case_id):
        assert payload["cui"] == cui, rel


def check_anaf_company(p: dict):
    for key in ("active", "vat_registered", "e_factura"):
        assert type(p[key]) is bool, key
    if p["vat_registered"]:
        assert is_iso_date(p["vat_since"])
    else:
        assert p["vat_since"] is None


def check_anaf_financials(p: dict):
    assert type(p["year"]) is int   # bool is an int subclass, so not isinstance
    assert p["currency"] == "RON"
    for key in MONEY_KEYS:
        assert type(p[key]) is int, key


def check_onrc_company(p: dict):
    for key in ("name", "reg_com", "status"):
        assert isinstance(p[key], str) and p[key], key
    assert list(p["address"]) == ADDRESS_KEYS
    assert all(isinstance(v, str) for v in p["address"].values())
    assert p["directors"]
    for d in p["directors"]:
        assert list(d) == DIRECTOR_KEYS
        assert isinstance(d["name"], str) and d["name"]
        assert type(d["can_sign"]) is bool


def check_court_cases(p: dict):
    assert isinstance(p["cases"], list)
    for c in p["cases"]:
        assert list(c) == COURT_CASE_KEYS
        assert c["category"] in CATEGORIES
        assert c["party_role"] in PARTY_ROLES
        assert c["stage"] in STAGES
        assert c["status"] in CASE_STATUSES
        assert is_iso_date(c["registered"])
        for key in ("number", "court", "subject", "other_party"):
            assert isinstance(c[key], str) and c[key], key


CHECKS = {
    "anaf_company": check_anaf_company,
    "anaf_financials": check_anaf_financials,
    "onrc_company": check_onrc_company,
    "court_cases": check_court_cases,
}


@pytest.mark.parametrize("case_id", list(load(MANIFEST)["cases"]))
def test_payload_keys_and_types(case_id: str):
    for tool, rel, p in payloads(MANIFEST, case_id):
        assert list(p) == KEYS[tool], rel
        assert p["source"] == SOURCE, rel
        assert isinstance(p["cui"], str) and cui_ok(p["cui"]), rel
        CHECKS[tool](p)


@pytest.mark.parametrize("case_id", list(load(MANIFEST)["cases"]))
def test_financials_one_payload_per_year(case_id: str):
    years = [p["year"] for tool, _, p in payloads(MANIFEST, case_id) if tool == "anaf_financials"]
    assert len(years) == len(set(years))
    assert 2024 in years
    # No case has 2025, so Role 2 must answer year=2025 with not_found.
    assert 2025 not in years


@pytest.mark.parametrize("manifest_path, case_id", CASES, ids=CASE_IDS)
def test_payload_wraps_in_tool_result(manifest_path: Path, case_id: str):
    """Shape only: each payload is valid ToolResult.data with status ok."""
    as_of = load(manifest_path)["as_of"]
    for i, (tool, rel, payload) in enumerate(payloads(manifest_path, case_id)):
        args = {"cui": payload["cui"]}
        if tool == "anaf_financials":
            args["year"] = payload["year"]
        result = ToolResult(
            id=f"t-{case_id}-{tool}-{i}",
            tool=tool,
            args=args,
            status="ok",
            data=payload,
            raw_ref=f"fixtures/registry/{rel}",
            fetched_at=as_of,
        )
        assert result.fetched_at.tzinfo is not None
        assert result.model_dump(mode="json")["data"] == payload


# ---------- the two required cases ----------

def demo(case_id: str) -> dict[str, list[dict]]:
    """tool -> list of payloads for one case of the default manifest."""
    out: dict[str, list[dict]] = {}
    for tool, _, p in payloads(MANIFEST, case_id):
        out.setdefault(tool, []).append(p)
    return out


def test_demo02_values():
    d = demo("DEMO-02")
    assert load(MANIFEST)["cases"]["DEMO-02"]["cui"] == "41738200"

    assert d["anaf_company"] == [{
        "source": SOURCE, "cui": "41738200", "active": True,
        "vat_registered": True, "vat_since": "2019-09-16", "e_factura": True,
    }]
    assert d["anaf_financials"] == [
        {"source": SOURCE, "cui": "41738200", "year": 2024, "currency": "RON",
         "turnover": 8100000, "total_revenue": 8240000, "total_expenses": 7690000, "net_profit": 462000},
        {"source": SOURCE, "cui": "41738200", "year": 2023, "currency": "RON",
         "turnover": 7350000, "total_revenue": 7420000, "total_expenses": 7010000, "net_profit": 344000},
    ]

    onrc = d["onrc_company"][0]
    assert onrc["name"] == "AGRO NORD TRANS SRL"
    assert onrc["reg_com"] == "J12/1834/2019"
    assert onrc["status"] == "funcțiune"
    assert onrc["directors"] == [{"name": "Andrei Mureșan", "can_sign": True}]

    assert d["court_cases"][0]["cases"] == [{
        "number": "2318/117/2025",
        "court": "Tribunalul Cluj",
        "subject": "executare silită",
        "category": "enforcement",
        "party_role": "debitor",
        "other_party": "LEASING FICTIV IFN SA",
        "stage": "executare",
        "status": "open",
        "registered": "2025-05-12",
    }]


@pytest.mark.parametrize("path", JSON_FILES, ids=lambda p: p.relative_to(REGISTRY).as_posix())
def test_no_pdf_turnover_or_difference_in_registry(path: Path):
    """12 400 000 is the PDF value and 4 300 000 the gap; neither belongs to the registry."""
    text = path.read_text(encoding="utf-8")
    for s in DEMO02_FORBIDDEN:
        assert s not in text


def test_demo01_values():
    d = demo("DEMO-01")
    assert d["court_cases"][0]["cases"] == []
    assert 2024 in [p["year"] for p in d["anaf_financials"]]


# ---------- leak guard ----------

def test_no_ground_truth_leaks_into_registry():
    files = [p for p in REGISTRY.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        for s in LEAK_STRINGS:
            assert s not in text, f"{path.relative_to(REGISTRY)} contains {s!r}"
