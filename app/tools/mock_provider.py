"""Arhitectură pluggable de provideri pentru registrele simulate (ANAF, ONRC, Portal Instanțe).

Consumă fixturile din `fixtures/registry/` (Rolul 1). Dacă folderul `fixtures/registry/` nu este încă
prezent pe disc, oferă un fallback sintetic local determinist.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import ToolStatus

from .normalization import normalize_cui

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES_DIR = _REPO_ROOT / "fixtures" / "registry"
DEFAULT_SIMULATED_TIMESTAMP = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class ProviderResponse:
    """Răspuns brut de la un provider de registru (înainte de normalizarea în ToolResult)."""

    status: ToolStatus
    payload: Any = None
    raw_ref: str | None = None
    case_id: str | None = None
    fetched_at: datetime = DEFAULT_SIMULATED_TIMESTAMP
    error: str | None = None


class RegistryProvider(ABC):
    """Interfață abstractă pentru interogarea registrelor (fixture provider acum, live provider ulterior)."""

    @abstractmethod
    def fetch_anaf_company(self, cui: str) -> ProviderResponse:
        """Returnează datele de identificare și TVA ale companiei de la ANAF."""

    @abstractmethod
    def fetch_anaf_financials(self, cui: str, year: int) -> ProviderResponse:
        """Returnează indicatorii din bilanțul depus la ANAF pentru anul `year`."""

    @abstractmethod
    def fetch_onrc_company(self, cui: str) -> ProviderResponse:
        """Returnează datele de înregistrare, administratori și asociați de la ONRC."""

    @abstractmethod
    def fetch_court_cases(self, cui: str) -> ProviderResponse:
        """Returnează dosarele de instanță asociate companiei."""


# Substituenți sintetici determiniști utilizați DOAR când `fixtures/registry/` nu există încă pe disc
_BUILTIN_SUBSTITUTES: dict[str, dict[str, Any]] = {
    "41738203": {
        "case_id": "DEMO-02",
        "anaf_company": {
            "cui": "41738203",
            "name": "AGRO NORD TRANS SRL",
            "reg_com": "J12/1834/2019",
            "address": "Str. Fabricii nr. 47, Cluj-Napoca, Jud. Cluj, 400632",
            "active": True,
            "inactive": False,
            "inactive_since": None,
            "vat_registered": True,
            "vat_since": "2019-10-01",
            "vat_cancelled": None,
            "e_factura": True,
            "split_vat": False,
            "cash_vat": False,
        },
        "anaf_financials": {
            "cui": "41738203",
            "financials": {
                "2024": {
                    "cui": "41738203",
                    "year": 2024,
                    "turnover": 8100000,
                    "total_revenue": 8240000,
                    "total_expenses": 7690000,
                    "net_profit": 462000,
                    "fixed_assets": 3100000,
                    "current_assets": 1900000,
                    "total_assets": 5000000,
                    "equity": 1450000,
                    "liabilities": 3550000,
                    "employees": 34,
                },
                "2023": {
                    "cui": "41738203",
                    "year": 2023,
                    "turnover": 7350000,
                    "total_revenue": 7420000,
                    "total_expenses": 7010000,
                    "net_profit": 344000,
                    "fixed_assets": 2800000,
                    "current_assets": 1600000,
                    "total_assets": 4400000,
                    "equity": 988000,
                    "liabilities": 3412000,
                    "employees": 31,
                },
            },
        },
        "onrc": {
            "company": {
                "name": "AGRO NORD TRANS SRL",
                "legal_form": "SRL",
                "cui": "41738203",
                "vat_prefix": True,
                "reg_com": "J12/1834/2019",
                "euid": "ROONRC.J12/1834/2019",
                "registration_date": "2019-09-16",
                "caen": {"code": "4941", "description": "Transporturi rutiere de mărfuri"},
                "address": {
                    "street": "Str. Fabricii",
                    "number": "47",
                    "city": "Cluj-Napoca",
                    "county": "Cluj",
                    "postal_code": "400632",
                },
                "onrc_status": "funcțiune",
                "share_capital_lei": 200,
            },
            "people": {
                "directors": [
                    {
                        "name": "Andrei Mureșan",
                        "role": "administrator",
                        "appointed": "2019-09-16",
                        "can_sign": True,
                    }
                ],
                "shareholders": [
                    {"name": "Andrei Mureșan", "type": "person", "percent": 60},
                    {"name": "Ioana Pop", "type": "person", "percent": 40},
                ],
                "ubos": [
                    {
                        "name": "Andrei Mureșan",
                        "birth_date": "1984-03-12",
                        "nationality": "RO",
                        "percent": 60,
                        "control": "direct",
                    },
                    {
                        "name": "Ioana Pop",
                        "birth_date": "1987-11-02",
                        "nationality": "RO",
                        "percent": 40,
                        "control": "direct",
                    },
                ],
            },
        },
        "court_cases": {
            "cui": "41738203",
            "company_name": "AGRO NORD TRANS SRL",
            "cases": [
                {
                    "number": "2318/117/2025",
                    "court": "Tribunalul Cluj",
                    "subject": "executare silită",
                    "category": "enforcement",
                    "party_role": "debitor",
                    "other_party": "LEASING FICTIV IFN SA",
                    "stage": "executare",
                    "status": "open",
                    "registered": "2025-05-12",
                }
            ],
        },
    },
    "14399840": {
        "case_id": "DEMO-01",
        "anaf_company": {
            "cui": "14399840",
            "name": "CARPATIA SOFTWARE SOLUTIONS SRL",
            "reg_com": "J40/4112/2018",
            "address": "Bd. Unirii nr. 15, București, Sector 3, 030822",
            "active": True,
            "inactive": False,
            "vat_registered": True,
            "vat_since": "2018-05-01",
            "vat_cancelled": None,
            "e_factura": True,
            "split_vat": False,
            "cash_vat": False,
        },
        "anaf_financials": {
            "cui": "14399840",
            "year": 2024,
            "turnover": 5200000,
            "total_revenue": 5300000,
            "total_expenses": 4400000,
            "net_profit": 756000,
            "fixed_assets": 1200000,
            "current_assets": 2100000,
            "total_assets": 3300000,
            "equity": 2400000,
            "liabilities": 900000,
            "employees": 22,
        },
        "onrc": {
            "cui": "14399840",
            "name": "CARPATIA SOFTWARE SOLUTIONS SRL",
            "legal_form": "SRL",
            "reg_com": "J40/4112/2018",
            "euid": "ROONRC.J40/4112/2018",
            "registration_date": "2018-04-12",
            "onrc_status": "funcțiune",
            "share_capital_lei": 1000,
            "address": "Bd. Unirii nr. 15, București, Sector 3, 030822",
            "directors": [
                {
                    "name": "Radu Ionescu",
                    "role": "administrator",
                    "appointed": "2018-04-12",
                    "can_sign": True,
                }
            ],
            "shareholders": [
                {"name": "Radu Ionescu", "type": "person", "percent": 100}
            ],
        },
        "court_cases": {
            "cui": "14399840",
            "company_name": "CARPATIA SOFTWARE SOLUTIONS SRL",
            "cases": [],
        },
    },
    "99999998": {
        "case_id": "DEMO-UNAVAILABLE",
        "anaf_company": {"status": "unavailable", "error": "Serviciul ANAF este indisponibil temporar (timeout)."},
        "anaf_financials": {"status": "unavailable", "error": "Serviciul ANAF Bilanț este indisponibil temporar."},
        "onrc": {"status": "unavailable", "error": "Serviciul ONRC este indisponibil temporar."},
        "court_cases": {"status": "unavailable", "error": "Portalul instanțelor (portal.just.ro) nu răspunde."},
    },
}


# Alias-uri de CUI între documentația Sprint 2 (41738203) și PDF-urile Sprint 1 (41738200)
_CUI_EQUIVALENTS: dict[str, str] = {
    "41738200": "41738203",
    "41738203": "41738200",
    "36182043": "14399840",
    "14399840": "36182043",
}
_BUILTIN_SUBSTITUTES["41738200"] = _BUILTIN_SUBSTITUTES["41738203"]
_BUILTIN_SUBSTITUTES["36182043"] = _BUILTIN_SUBSTITUTES["14399840"]


class FixtureRegistryProvider(RegistryProvider):
    """Provider care citește fixturile JSON din `fixtures/registry/` (Rolul 1)."""

    def __init__(
        self,
        fixtures_dir: str | Path | None = None,
        *,
        allow_builtin_fallback: bool | None = None,
        default_fetched_at: datetime = DEFAULT_SIMULATED_TIMESTAMP,
    ) -> None:
        if fixtures_dir is None:
            self.fixtures_dir = DEFAULT_FIXTURES_DIR
            self.allow_builtin_fallback = (
                True if allow_builtin_fallback is None else allow_builtin_fallback
            )
        else:
            self.fixtures_dir = Path(fixtures_dir)
            self.allow_builtin_fallback = (
                False if allow_builtin_fallback is None else allow_builtin_fallback
            )
        self.default_fetched_at = default_fetched_at

    def _to_raw_ref(self, file_path: Path) -> str:
        """Construiește o referință relativă POSIX către fișierul sursă (ex. `fixtures/registry/DEMO-02/onrc.json`)."""
        try:
            return file_path.resolve().relative_to(_REPO_ROOT.resolve()).as_posix()
        except ValueError:
            try:
                rel = file_path.resolve().relative_to(self.fixtures_dir.resolve()).as_posix()
                return f"fixtures/registry/{rel}"
            except ValueError:
                return file_path.as_posix()

    def _load_manifest_mapping(self) -> dict[str, Path]:
        """Construiește maparea {normalized_cui: folder_path} din `cases_manifest.json` și din subfoldere."""
        mapping: dict[str, Path] = {}
        if not self.fixtures_dir.exists():
            return mapping

        # 1. Citim cases_manifest.json sau manifest.json dacă există
        for manifest_name in ("cases_manifest.json", "manifest.json"):
            manifest_path = self.fixtures_dir / manifest_name
            if manifest_path.is_file():
                try:
                    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    self._parse_manifest_entries(raw_manifest, mapping)
                except Exception:
                    pass

        # 2. Scanăm și directoarele din fixtures/registry/ (ex. DEMO-02/) pentru rezoluție directă după CUI
        for child in sorted(self.fixtures_dir.iterdir()):
            if not child.is_dir():
                continue
            # Dacă numele directorului este chiar un CUI
            try:
                cui_dir = normalize_cui(child.name)
                mapping.setdefault(cui_dir, child)
            except ValueError:
                pass

            # Inspectăm fișierele din subdirector pentru a afla CUI-ul cazului
            for candidate_name in ("anaf_company.json", "onrc.json", "anaf_financials.json", "court_cases.json"):
                cand_file = child / candidate_name
                if cand_file.is_file():
                    try:
                        data = json.loads(cand_file.read_text(encoding="utf-8"))
                        cui_val = self._extract_cui_from_json(data)
                        if cui_val:
                            mapping.setdefault(cui_val, child)
                    except Exception:
                        continue

        return mapping

    def _parse_manifest_entries(self, raw_manifest: Any, mapping: dict[str, Path]) -> None:
        if isinstance(raw_manifest, dict):
            # Caz A: {"by_cui": {"41738203": "DEMO-02" sau {...}}}
            by_cui = raw_manifest.get("by_cui") or raw_manifest.get("cui_map")
            if isinstance(by_cui, dict):
                for k, v in by_cui.items():
                    self._register_manifest_pair(k, v, mapping)

            # Caz B: {"cases": [...] sau {...}}
            cases = raw_manifest.get("cases")
            if isinstance(cases, (dict, list)):
                self._parse_manifest_entries(cases, mapping)

            # Caz C: mapare directă la rădăcină {"DEMO-02": {"cui": "41738203", ...}} sau {"41738203": "DEMO-02"}
            for k, v in raw_manifest.items():
                if k in ("by_cui", "cui_map", "cases", "version", "generated_at"):
                    continue
                self._register_manifest_pair(k, v, mapping)

        elif isinstance(raw_manifest, list):
            for entry in raw_manifest:
                if isinstance(entry, dict):
                    cui_raw = entry.get("cui")
                    target = (
                        entry.get("path")
                        or entry.get("dir")
                        or entry.get("folder")
                        or entry.get("case_id")
                        or entry.get("id")
                    )
                    if cui_raw and target:
                        self._register_manifest_pair(str(cui_raw), target, mapping)

    def _register_manifest_pair(self, key: str, value: Any, mapping: dict[str, Path]) -> None:
        # key poate fi CUI sau case_id
        try:
            norm_cui = normalize_cui(key)
            if isinstance(value, str):
                folder = self._resolve_folder_ref(value)
                mapping[norm_cui] = folder
            elif isinstance(value, dict):
                target = (
                    value.get("path")
                    or value.get("dir")
                    or value.get("folder")
                    or value.get("case_id")
                    or value.get("id")
                )
                if target:
                    mapping[norm_cui] = self._resolve_folder_ref(str(target))
            return
        except ValueError:
            pass

        # Dacă key este case_id (ex. "DEMO-02") și value este dict cu "cui"
        if isinstance(value, dict) and value.get("cui"):
            try:
                norm_cui = normalize_cui(value["cui"])
                target = value.get("path") or value.get("dir") or value.get("folder") or key
                mapping[norm_cui] = self._resolve_folder_ref(str(target))
            except ValueError:
                pass

    def _resolve_folder_ref(self, ref: str) -> Path:
        ref_path = Path(ref)
        if ref_path.is_absolute() and ref_path.exists():
            return ref_path
        cand1 = self.fixtures_dir / ref_path
        if cand1.exists():
            return cand1
        cand2 = _REPO_ROOT / ref_path
        if cand2.exists():
            return cand2
        return self.fixtures_dir / ref_path.name

    @staticmethod
    def _extract_cui_from_json(data: Any) -> str | None:
        if not isinstance(data, dict):
            return None
        raw_cui = (
            data.get("cui")
            or (data.get("company") or {}).get("cui")
            if isinstance(data.get("company"), dict)
            else data.get("cui")
        )
        if not raw_cui:
            return None
        try:
            return normalize_cui(raw_cui)
        except ValueError:
            return None

    def _find_fixture_file(
        self, norm_cui: str, filenames: tuple[str, ...], tool_subfolder: str
    ) -> tuple[Path | None, str | None]:
        """Caută fișierul fixture pentru `norm_cui` și returnează `(file_path, case_id)`."""
        if not self.fixtures_dir.exists():
            return None, None

        mapping = self._load_manifest_mapping()
        case_folder = mapping.get(norm_cui) or mapping.get(
            _CUI_EQUIVALENTS.get(norm_cui, "")
        )
        if case_folder and case_folder.is_dir():
            for fname in filenames:
                fpath = case_folder / fname
                if fpath.is_file():
                    return fpath, case_folder.name
            # Dacă folderul cazului există în manifest dar fișierul specific lipsește,
            # returnăm (None, case_folder.name) pentru a semnaliza indisponibilitatea acelui registru
            return None, case_folder.name

        # Fallback: structură pe subfoldere de tool `fixtures/registry/<tool>/<cui>.json`
        tool_dir = self.fixtures_dir / tool_subfolder
        if tool_dir.is_dir():
            for fname in (f"{norm_cui}.json", *filenames):
                fpath = tool_dir / fname
                if fpath.is_file():
                    return fpath, None

        return None, None

    def _read_fixture_response(
        self,
        norm_cui: str,
        filenames: tuple[str, ...],
        tool_subfolder: str,
        builtin_key: str,
    ) -> ProviderResponse:
        # 1. Căutăm în `fixtures/registry/` pe disc
        if self.fixtures_dir.exists():
            fpath, case_id = self._find_fixture_file(norm_cui, filenames, tool_subfolder)
            if fpath is not None and fpath.is_file():
                raw_ref = self._to_raw_ref(fpath)
                try:
                    raw_text = fpath.read_text(encoding="utf-8")
                    payload = json.loads(raw_text)
                except Exception as exc:
                    return ProviderResponse(
                        status="unavailable",
                        payload=None,
                        raw_ref=raw_ref,
                        case_id=case_id,
                        fetched_at=self.default_fetched_at,
                        error=f"Fișierul fixture {raw_ref} este malformat sau nu poate fi parsat: {exc}",
                    )
                return self._interpret_payload(payload, raw_ref=raw_ref, case_id=case_id)

            # Dacă dosarul există în manifest/director, dar lipsește fișierul pentru acest registru (scenariu incomplet/indisponibil)
            if case_id is not None:
                expected_ref = f"fixtures/registry/{case_id}/{filenames[0]}"
                return ProviderResponse(
                    status="unavailable",
                    payload=None,
                    raw_ref=expected_ref,
                    case_id=case_id,
                    fetched_at=self.default_fetched_at,
                    error=f"Registrul simulat '{builtin_key}' este indisponibil (fișierul {expected_ref} lipsește).",
                )

            if not self.allow_builtin_fallback:
                return ProviderResponse(
                    status="not_found",
                    payload=None,
                    raw_ref=None,
                    case_id=None,
                    fetched_at=self.default_fetched_at,
                    error=f"Nu există înregistrări în registrul simulat '{builtin_key}' pentru CUI {norm_cui}.",
                )

        # 2. Fallback pe substituenții sintetici predefiniți (când Rolul 1 nu este încă integrat)
        if self.allow_builtin_fallback and norm_cui in _BUILTIN_SUBSTITUTES:
            entry = _BUILTIN_SUBSTITUTES[norm_cui]
            case_id = str(entry.get("case_id") or norm_cui)
            raw_ref = f"fixtures/registry/{case_id}/{filenames[0]}"
            if builtin_key not in entry or entry[builtin_key] is None:
                return ProviderResponse(
                    status="unavailable",
                    payload=None,
                    raw_ref=raw_ref,
                    case_id=case_id,
                    fetched_at=self.default_fetched_at,
                    error=f"Registrul simulat '{builtin_key}' este indisponibil pentru {case_id}.",
                )
            return self._interpret_payload(
                entry[builtin_key], raw_ref=raw_ref, case_id=case_id
            )

        # Dacă directorul de fixturi specificat explicit nu există deloc pe disc
        if not self.fixtures_dir.exists() and not self.allow_builtin_fallback:
            return ProviderResponse(
                status="unavailable",
                payload=None,
                raw_ref=None,
                case_id=None,
                fetched_at=self.default_fetched_at,
                error=f"Directorul de fixturi {self.fixtures_dir} nu este disponibil.",
            )

        return ProviderResponse(
            status="not_found",
            payload=None,
            raw_ref=None,
            case_id=None,
            fetched_at=self.default_fetched_at,
            error=f"CUI {norm_cui} nu a fost găsit în registrul simulat '{builtin_key}'.",
        )

    def _interpret_payload(
        self, payload: Any, *, raw_ref: str | None, case_id: str | None
    ) -> ProviderResponse:
        fetched_at = self.default_fetched_at
        if isinstance(payload, dict):
            # Extragem timestamp-ul din fixture dacă este specificat
            raw_ts = payload.get("fetched_at") or payload.get("timestamp")
            if isinstance(raw_ts, str):
                try:
                    fetched_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except ValueError:
                    pass

            explicit_status = payload.get("status")
            if explicit_status == "unavailable" or payload.get("available") is False:
                err_msg = str(
                    payload.get("error")
                    or payload.get("message")
                    or "Registrul simulat a raportat starea 'unavailable'."
                )
                return ProviderResponse(
                    status="unavailable",
                    payload=None,
                    raw_ref=raw_ref,
                    case_id=case_id,
                    fetched_at=fetched_at,
                    error=err_msg,
                )
            if explicit_status == "not_found":
                err_msg = str(
                    payload.get("error")
                    or payload.get("message")
                    or "Entitatea nu a fost găsită în registrul simulat."
                )
                return ProviderResponse(
                    status="not_found",
                    payload=None,
                    raw_ref=raw_ref,
                    case_id=case_id,
                    fetched_at=fetched_at,
                    error=err_msg,
                )

            # Dacă payload-ul are un wrapper {"status": "ok", "data": {...}}, despachetăm "data"
            if (
                explicit_status == "ok"
                and "data" in payload
                and isinstance(payload["data"], (dict, list))
            ):
                payload = payload["data"]

        return ProviderResponse(
            status="ok",
            payload=payload,
            raw_ref=raw_ref,
            case_id=case_id,
            fetched_at=fetched_at,
            error=None,
        )

    def fetch_anaf_company(self, cui: str) -> ProviderResponse:
        norm_cui = normalize_cui(cui)
        return self._read_fixture_response(
            norm_cui,
            filenames=("anaf_company.json",),
            tool_subfolder="anaf_company",
            builtin_key="anaf_company",
        )

    def fetch_anaf_financials(self, cui: str, year: int) -> ProviderResponse:
        norm_cui = normalize_cui(cui)
        return self._read_fixture_response(
            norm_cui,
            filenames=("anaf_financials.json", f"anaf_financials_{year}.json"),
            tool_subfolder="anaf_financials",
            builtin_key="anaf_financials",
        )

    def fetch_onrc_company(self, cui: str) -> ProviderResponse:
        norm_cui = normalize_cui(cui)
        return self._read_fixture_response(
            norm_cui,
            filenames=("onrc.json", "onrc_company.json"),
            tool_subfolder="onrc",
            builtin_key="onrc",
        )

    def fetch_court_cases(self, cui: str) -> ProviderResponse:
        norm_cui = normalize_cui(cui)
        return self._read_fixture_response(
            norm_cui,
            filenames=("court_cases.json", "court.json"),
            tool_subfolder="court_cases",
            builtin_key="court_cases",
        )


# Alias pentru compatibilitate cu denumirea modulului
MockRegistryProvider = FixtureRegistryProvider
