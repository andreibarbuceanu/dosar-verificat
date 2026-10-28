from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.models import ToolResult  # noqa: E402
from app.tools import (  # noqa: E402
    FixtureRegistryProvider,
    get_anaf_company,
    get_anaf_financials,
    get_court_cases,
    get_onrc_company,
    is_valid_cui_format,
    normalize_company_name,
    normalize_cui,
    query_all_registries,
    validate_cui_checksum,
)


def test_cui_and_name_normalization() -> None:
    """Verifică normalizarea CUI (inclusiv prefix RO), cifra de control și denumirile de companii."""
    assert normalize_cui("RO41738203") == "41738203"
    assert normalize_cui(" ro - 41738203 ") == "41738203"
    assert normalize_cui(41738203) == "41738203"
    assert validate_cui_checksum("41738200") is True
    assert validate_cui_checksum("RO41738200") is True
    assert validate_cui_checksum("41738203") is False

    assert is_valid_cui_format("RO41738203") is True
    assert is_valid_cui_format("INVALID") is False
    assert is_valid_cui_format("") is False

    assert (
        normalize_company_name("  S.C. Agro Nord Trans S.R.L. ")
        == "AGRO NORD TRANS SRL"
    )
    assert (
        normalize_company_name("Mureşan & Ţară S.A.")
        == "MUREȘAN & ȚARĂ SA"
    )


def test_demo_02_builtin_substitutes() -> None:
    """Verifică scenariul DEMO-02 (AGRO NORD TRANS SRL, CUI 41738203) și contractul ToolResult."""
    fin = get_anaf_financials("RO41738203", 2024)
    assert isinstance(fin, ToolResult)
    assert fin.id == "tool-demo02-financials"
    assert fin.tool == "anaf_financials"
    assert fin.args == {"cui": "41738203", "year": 2024}
    assert fin.status == "ok"
    assert fin.data is not None
    assert fin.data["cui"] == "41738203"
    assert fin.data["year"] == 2024
    assert fin.data["turnover"] == 8100000
    assert fin.data["net_profit"] == 462000
    assert fin.data["source_mode"] == "simulated_fixture"
    assert fin.raw_ref == "fixtures/registry/DEMO-02/anaf_financials.json"

    comp = get_anaf_company("41738203")
    assert isinstance(comp, ToolResult)
    assert comp.status == "ok"
    assert comp.data is not None
    assert comp.data["name"] == "AGRO NORD TRANS SRL"
    assert comp.data["active"] is True
    assert comp.data["inactive"] is False
    assert comp.data["vat_registered"] is True
    assert comp.data["e_factura"] is True

    onrc = get_onrc_company("41738203")
    assert isinstance(onrc, ToolResult)
    assert onrc.status == "ok"
    assert onrc.data is not None
    assert onrc.data["reg_com"] == "J12/1834/2019"
    assert onrc.data["status"] == "funcțiune"
    assert onrc.data["onrc_status"] == "funcțiune"
    assert len(onrc.data["directors"]) == 1
    assert onrc.data["directors"][0]["name"] == "Andrei Mureșan"
    assert len(onrc.data["shareholders"]) == 2

    court = get_court_cases("41738203")
    assert isinstance(court, ToolResult)
    assert court.status == "ok"
    assert court.data is not None
    assert court.data["open_cases_count"] == 1
    assert court.data["has_open_enforcement"] is True
    assert court.data["cases"][0]["number"] == "2318/117/2025"
    assert court.data["cases"][0]["category"] == "enforcement"

    all_results = query_all_registries("41738203", 2024)
    assert len(all_results) == 4
    assert all(r.status == "ok" for r in all_results)


def test_role1_disk_fixtures_and_manifest(tmp_path: Path) -> None:
    """Verifică citirea fixturilor de pe disc și a manifestului `cases_manifest.json` (formatul Rolului 1)."""
    reg_dir = tmp_path / "registry"
    case_dir = reg_dir / "DEMO-02"
    case_dir.mkdir(parents=True)

    manifest = {
        "cases": {
            "DEMO-02": {
                "cui": "41738203",
                "paths": {
                    "anaf_company": "DEMO-02/anaf_company.json",
                    "anaf_financials": "DEMO-02/anaf_financials.json",
                    "onrc_company": "DEMO-02/onrc.json",
                    "court_cases": "DEMO-02/court_cases.json",
                },
            }
        }
    }
    (reg_dir / "cases_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    (case_dir / "anaf_company.json").write_text(
        json.dumps(
            {
                "cui": "41738203",
                "name": "AGRO NORD TRANS SRL",
                "active": True,
                "vat_registered": True,
                "e_factura": True,
                "fetched_at": "2026-10-20T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "anaf_financials.json").write_text(
        json.dumps(
            {
                "cui": "41738203",
                "year": 2024,
                "turnover": 8100000,
                "net_profit": 462000,
                "fetched_at": "2026-10-20T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "onrc.json").write_text(
        json.dumps(
            {
                "cui": "41738203",
                "name": "AGRO NORD TRANS SRL",
                "reg_com": "J12/1834/2019",
                "directors": [{"name": "Andrei Mureșan", "role": "administrator"}],
                "shareholders": [{"name": "Andrei Mureșan", "percent": 60}],
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "court_cases.json").write_text(
        json.dumps(
            {
                "cui": "41738203",
                "cases": [
                    {
                        "number": "2318/117/2025",
                        "court": "Tribunalul Cluj",
                        "subject": "executare silită",
                        "category": "enforcement",
                        "party_role": "debitor",
                        "stage": "executare",
                        "status": "open",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    provider = FixtureRegistryProvider(fixtures_dir=reg_dir)
    fin = get_anaf_financials("41738203", 2024, provider=provider)
    assert fin.status == "ok"
    assert fin.id == "tool-demo02-financials"
    assert fin.data is not None
    assert fin.data["turnover"] == 8100000
    assert fin.raw_ref == "fixtures/registry/DEMO-02/anaf_financials.json"

    # An fiscal inexistent în fixture -> not_found (data=None conform SPRINT2_CONTRACT.md)
    fin_2019 = get_anaf_financials("41738203", 2019, provider=provider)
    assert fin_2019.status == "not_found"
    assert fin_2019.data is None


def test_missing_unavailable_and_malformed_responses(tmp_path: Path) -> None:
    """Verifică distincția strictă între `not_found` și `unavailable` (inclusiv JSON malformat)."""
    reg_dir = tmp_path / "registry"
    broken_dir = reg_dir / "BROKEN-01"
    broken_dir.mkdir(parents=True)

    manifest = {
        "BROKEN-01": {"cui": "55667788", "path": "BROKEN-01"},
    }
    (reg_dir / "cases_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    # 1. anaf_company.json cu JSON corupt -> unavailable
    (broken_dir / "anaf_company.json").write_text("{corrupt json", encoding="utf-8")

    # 2. anaf_financials.json fără câmpul obligatoriu 'turnover' -> unavailable (malformat)
    (broken_dir / "anaf_financials.json").write_text(
        json.dumps({"cui": "55667788", "year": 2024, "net_profit": 1000}),
        encoding="utf-8",
    )

    # 3. onrc.json cu status explicit unavailable -> unavailable
    (broken_dir / "onrc.json").write_text(
        json.dumps({"status": "unavailable", "error": "ONRC service timeout"}),
        encoding="utf-8",
    )

    # 4. court_cases.json lipsește complet din folderul BROKEN-01 -> unavailable
    provider = FixtureRegistryProvider(fixtures_dir=reg_dir)

    res_comp = get_anaf_company("55667788", provider=provider)
    assert res_comp.status == "unavailable"
    assert res_comp.data is None

    res_fin = get_anaf_financials("55667788", 2024, provider=provider)
    assert res_fin.status == "unavailable"
    assert res_fin.data is None

    res_onrc = get_onrc_company("55667788", provider=provider)
    assert res_onrc.status == "unavailable"
    assert res_onrc.data is None

    res_court = get_court_cases("55667788", provider=provider)
    assert res_court.status == "unavailable"
    assert res_court.data is None
    assert res_court.raw_ref == "fixtures/registry/BROKEN-01/court_cases.json"

    # 5. CUI care nu există în manifest/fixturi -> not_found
    res_missing = get_anaf_company("12345678", provider=provider)
    assert res_missing.status == "not_found"
    assert res_missing.data is None

    # 6. CUI cu format invalid -> not_found
    res_invalid = get_anaf_company("NOT-A-CUI", provider=provider)
    assert res_invalid.status == "not_found"
    assert res_invalid.data is None


def test_no_ground_truth_access_in_tools_module() -> None:
    """Verifică regula de securitate: `app/tools/` nu citește `companies.json`, `expected` sau `planted_errors`."""
    tools_dir = _REPO_ROOT / "app" / "tools"
    forbidden_tokens = ("planted_errors", "intake_truth.json", "companies.json", "ground_truth")
    for py_file in tools_dir.glob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        # Eliminăm docstring-urile și comentariile pentru a verifica strict codul executabil
        code_lines = [
            line
            for line in source.splitlines()
            if not line.strip().startswith("#") and not line.strip().startswith('"""')
        ]
        code_body = "\n".join(code_lines)
        for token in forbidden_tokens:
            assert token not in code_body, f"Token interzis {token!r} găsit în {py_file.name}"


class RegistryToolsTestCase(unittest.TestCase):
    """Compatibilitate și cu `python -m unittest` și cu `pytest`."""

    def test_all_registry_tools_scenarios(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="dosar_tools_ut_"))
        test_cui_and_name_normalization()
        test_demo_02_builtin_substitutes()
        test_role1_disk_fixtures_and_manifest(tmp / "t1")
        test_missing_unavailable_and_malformed_responses(tmp / "t2")
        test_no_ground_truth_access_in_tools_module()


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="dosar_tools_test_"))
    test_cui_and_name_normalization()
    test_demo_02_builtin_substitutes()
    test_role1_disk_fixtures_and_manifest(tmp / "t1")
    test_missing_unavailable_and_malformed_responses(tmp / "t2")
    test_no_ground_truth_access_in_tools_module()
    print("Toate cele 5 teste din tests/tools/test_registry_tools.py au trecut cu succes!")
