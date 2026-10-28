"""
fixtures/registry/build_fixtures.py — one-off generator for the synthetic registry fixtures.

Reads companies.json (repo root), keeps ONLY the registry-side keys
(company, anaf, financials, people, court_cases) and writes the payloads of
docs/SPRINT2_CONTRACT.md §3 (v1.0). The JSON files are the deliverable; this
script just makes them reproducible. Same input -> byte-identical output.

    python fixtures/registry/build_fixtures.py           # (re)write the files
    python fixtures/registry/build_fixtures.py --check   # exit 1 if any file is stale
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPANIES = HERE.parents[1] / "companies.json"

AS_OF = "2026-10-20T00:00:00+00:00"
SOURCE = "synthetic_fixture"
CURRENCY = "RON"

# The only companies.json keys this script may touch; everything else is dropped on load.
ALLOWED_KEYS = ("company", "anaf", "financials", "people", "court_cases")

# Manifest key (= ToolResult.tool) -> file name in the case folder.
FILES = {
    "anaf_company": "anaf_company.json",
    "anaf_financials": "anaf_financials.json",
    "onrc_company": "onrc.json",
    "court_cases": "court_cases.json",
}

ANAF_KEYS = ("active", "vat_registered", "vat_since", "e_factura")
MONEY_KEYS = ("turnover", "total_revenue", "total_expenses", "net_profit")
COURT_CASE_KEYS = (
    "number", "court", "subject", "category", "party_role",
    "other_party", "stage", "status", "registered",
)

# Same company as DEMO-01, but the manifest has no anaf_financials path.
INCOMPLETE_CASE = "DEMO-01-INCOMPLETE"
INCOMPLETE_BASE = "DEMO-01"


def load_companies() -> dict[str, dict]:
    """Case ID -> {allowed key: value}, in companies.json order."""
    with COMPANIES.open(encoding="utf-8") as f:
        entries = json.load(f)
    return {e["id"]: {k: e[k] for k in ALLOWED_KEYS} for e in entries}


def anaf_company(c: dict) -> dict:
    return {"source": SOURCE, "cui": c["company"]["cui"], **{k: c["anaf"][k] for k in ANAF_KEYS}}


def anaf_financials(c: dict) -> list[dict]:
    """One payload per fiscal year, newest first."""
    return [
        {
            "source": SOURCE,
            "cui": c["company"]["cui"],
            "year": int(year),
            "currency": CURRENCY,
            **{k: c["financials"][year][k] for k in MONEY_KEYS},
        }
        for year in sorted(c["financials"], key=int, reverse=True)
    ]


def onrc_company(c: dict) -> dict:
    company = c["company"]
    return {
        "source": SOURCE,
        "cui": company["cui"],
        "name": company["name"],
        "reg_com": company["reg_com"],
        "status": company["onrc_status"],
        "address": dict(company["address"]),
        "directors": [{"name": d["name"], "can_sign": d["can_sign"]} for d in c["people"]["directors"]],
    }


def court_cases(c: dict) -> dict:
    return {
        "source": SOURCE,
        "cui": c["company"]["cui"],
        "cases": [{k: case[k] for k in COURT_CASE_KEYS} for case in c["court_cases"]],
    }


BUILDERS = {
    "anaf_company": anaf_company,
    "anaf_financials": anaf_financials,
    "onrc_company": onrc_company,
    "court_cases": court_cases,
}


def dump(obj) -> bytes:
    # ensure_ascii=False keeps the diacritics readable; LF only, trailing newline.
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build() -> dict[Path, bytes]:
    """Every output file -> its exact bytes."""
    out: dict[Path, bytes] = {}
    cases: dict[str, dict] = {}
    for case_id, c in load_companies().items():
        paths = {}
        for key, name in FILES.items():
            out[HERE / case_id / name] = dump(BUILDERS[key](c))
            paths[key] = f"{case_id}/{name}"
        cases[case_id] = {"cui": c["company"]["cui"], "paths": paths}

    out[HERE / "cases_manifest.json"] = dump({"as_of": AS_OF, "cases": cases})

    base = cases[INCOMPLETE_BASE]
    incomplete = {
        "cui": base["cui"],
        "paths": {k: v for k, v in base["paths"].items() if k != "anaf_financials"},
    }
    out[HERE / "cases_manifest.incomplete.json"] = dump({"as_of": AS_OF, "cases": {INCOMPLETE_CASE: incomplete}})
    return out


def main(argv: list[str]) -> int:
    files = build()
    if "--check" in argv:
        stale = [p for p, data in files.items() if not p.exists() or p.read_bytes() != data]
        for p in stale:
            print("stale:", p.relative_to(HERE))
        print(f"{len(files) - len(stale)}/{len(files)} files up to date")
        return 1 if stale else 0

    for p, data in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)   # bytes, so Windows cannot turn \n into \r\n
    print(f"wrote {len(files)} files under {HERE}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
