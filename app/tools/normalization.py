"""Normalizare deterministă pentru CUI, denumiri de companii și răspunsuri din registre simulate.

Acest modul este pur funcțional și nu apelează servicii externe.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_CEDILLA_TO_COMMA = str.maketrans(
    {
        "ş": "ș",
        "Ş": "Ș",
        "ţ": "ț",
        "Ţ": "Ț",
        "\xa0": " ",
        "\u200b": "",
        "„": '"',
        "”": '"',
        "“": '"',
        "’": "'",
        "‘": "'",
        "\u2013": "-",
        "\u2014": "-",
    }
)

_LEGAL_FORM_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bS\s*\.\s*R\s*\.\s*L\s*\.?\b", re.IGNORECASE), "SRL"),
    (re.compile(r"\bS\s*\.\s*A\s*\.?\b", re.IGNORECASE), "SA"),
    (re.compile(r"\bS\s*\.\s*N\s*\.\s*C\s*\.?\b", re.IGNORECASE), "SNC"),
    (re.compile(r"\bS\s*\.\s*C\s*\.\s*S\s*\.?\b", re.IGNORECASE), "SCS"),
    (re.compile(r"\bP\s*\.\s*F\s*\.\s*A\s*\.?\b", re.IGNORECASE), "PFA"),
    (re.compile(r"\bI\s*\.\s*F\s*\.\s*N\s*\.?\b", re.IGNORECASE), "IFN"),
]


def normalize_cui(cui: str | int | None) -> str:
    """Curăță și normalizează un CUI românesc la șirul de cifre (fără prefixul 'RO').

    Exemple:
        "RO41738203" -> "41738203"
        " ro 41738203 " -> "41738203"
        41738203 -> "41738203"

    Ridică ``ValueError`` dacă valoarea este goală sau nu reprezintă un CUI valid numeric (2..10 cifre).
    """
    if cui is None or isinstance(cui, bool):
        raise ValueError("CUI-ul nu poate fi nul sau boolean.")

    raw = str(cui).strip()
    if not raw:
        raise ValueError("CUI-ul este gol.")

    # Eliminăm prefixul opțional CUI / CIF / RO și separatoarele uzuale
    cleaned = re.sub(r"^(?:C\.?U\.?I\.?|C\.?I\.?F\.?)\s*[:\-]?\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"^RO\s*[\-:]?\s*", "", cleaned.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"[\s\-.]", "", cleaned)

    if not cleaned.isdigit() or not (2 <= len(cleaned) <= 10):
        raise ValueError(f"Format CUI invalid: {cui!r}")

    return cleaned


def is_valid_cui_format(cui: str | int | None) -> bool:
    """Returnează True dacă `cui` poate fi normalizat la un șir numeric valid (2..10 cifre)."""
    try:
        normalize_cui(cui)
        return True
    except ValueError:
        return False


def validate_cui_checksum(cui: str | int) -> bool:
    """Verifică cifra de control a unui CUI românesc folosind cheia standard 753217532."""
    try:
        digits = normalize_cui(cui)
    except ValueError:
        return False

    if len(digits) < 2 or len(digits) > 10:
        return False

    weights = [7, 5, 3, 2, 1, 7, 5, 3, 2]
    number_part = digits[:-1].zfill(9)
    check_digit = int(digits[-1])

    total = sum(int(d) * w for d, w in zip(number_part, weights))
    remainder = (total * 10) % 11
    expected = 0 if remainder == 10 else remainder
    return check_digit == expected


def normalize_text_value(value: str | None) -> str:
    """Normalizează diacriticele românești (ș/ț cu virgulă) și spațiile multiple."""
    if not value:
        return ""
    text = unicodedata.normalize("NFC", str(value)).translate(_CEDILLA_TO_COMMA)
    return re.sub(r"\s+", " ", text).strip()


def normalize_company_name(name: str | None) -> str:
    """Normalizează denumirea unei companii (diacritice, spații, forma juridică SRL/SA)."""
    text = normalize_text_value(name)
    if not text:
        return ""
    # Eliminăm prefixul opțional "S.C." / "SC " de la începutul denumirii
    text = re.sub(r"^S\.?\s*C\.?\s+", "", text, flags=re.IGNORECASE)
    for pattern, replacement in _LEGAL_FORM_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"\s+", " ", text).strip(" ,.-")
    return text.upper()


def normalize_person_name(name: str | None) -> str:
    """Normalizează numele unei persoane păstrând diacriticele cu virgulă."""
    return normalize_text_value(name)


def _format_address_str(addr: str | dict[str, Any] | None) -> str:
    """Returnează o reprezentare text uniformă a adresei, indiferent dacă în fixture e dict sau str."""
    if not addr:
        return ""
    if isinstance(addr, str):
        return normalize_text_value(addr)
    if isinstance(addr, dict):
        parts: list[str] = []
        street = addr.get("street") or addr.get("strada")
        number = addr.get("number") or addr.get("nr")
        city = addr.get("city") or addr.get("localitate")
        county = addr.get("county") or addr.get("judet")
        postal_code = addr.get("postal_code") or addr.get("cod_postal")
        if street:
            s = normalize_text_value(str(street))
            if number:
                s = f"{s} nr. {normalize_text_value(str(number))}"
            parts.append(s)
        if city:
            parts.append(normalize_text_value(str(city)))
        if county:
            c_str = normalize_text_value(str(county))
            if not c_str.lower().startswith("jud"):
                c_str = f"Jud. {c_str}"
            parts.append(c_str)
        if postal_code:
            parts.append(normalize_text_value(str(postal_code)))
        return ", ".join(parts)
    return normalize_text_value(str(addr))


def _coerce_number(val: Any) -> int | float | None:
    """Convertește sume financiare sau întregi la int/float; returnează None dacă lipsește."""
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and val.is_integer():
            return int(val)
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        s = re.sub(r"(?i)\b(ron|lei|eur)\b", "", s).strip()
        s = s.replace(" ", "").replace("\xa0", "")
        if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", s):
            s = s.replace(".", "")
        elif re.fullmatch(r"-?\d{1,3}(?:,\d{3})+", s):
            s = s.replace(",", "")
        elif "," in s and "." not in s:
            s = s.replace(",", ".")
        num = float(s)
        return int(num) if num.is_integer() else num
    raise ValueError(f"Valoare numerică invalidă: {val!r}")


def normalize_anaf_company_payload(raw: dict[str, Any], requested_cui: str) -> dict[str, Any]:
    """Normalizează datele despre companie și TVA din registrul simulat ANAF."""
    if not isinstance(raw, dict):
        raise ValueError("Răspunsul anaf_company trebuie să fie un obiect JSON (dict).")

    nested_anaf = raw.get("anaf") if isinstance(raw.get("anaf"), dict) else {}
    nested_comp = raw.get("company") if isinstance(raw.get("company"), dict) else {}
    merged = {**nested_comp, **nested_anaf, **raw}

    norm_cui = normalize_cui(requested_cui or merged.get("cui"))

    raw_name = merged.get("name") or merged.get("company_name") or merged.get("denumire") or ""
    norm_name = normalize_company_name(str(raw_name)) if raw_name else ""

    # Determinăm starea active / inactive
    if "active" in merged and merged["active"] is not None:
        if not isinstance(merged["active"], bool):
            raise ValueError("Câmpul 'active' trebuie să fie boolean.")
        active = bool(merged["active"])
        inactive = not active
    elif "inactive" in merged and merged["inactive"] is not None:
        if not isinstance(merged["inactive"], bool):
            raise ValueError("Câmpul 'inactive' trebuie să fie boolean.")
        inactive = bool(merged["inactive"])
        active = not inactive
    elif "status_inactivi" in merged and merged["status_inactivi"] is not None:
        inactive = bool(merged["status_inactivi"])
        active = not inactive
    else:
        active = True
        inactive = False

    vat_registered = bool(
        merged.get("vat_registered", merged.get("scpTVA", False))
    )
    e_factura = bool(
        merged.get("e_factura", merged.get("statusRO_e_Factura", False))
    )
    split_vat = bool(merged.get("split_vat", False))
    cash_vat = bool(merged.get("cash_vat", merged.get("statusTvaIncasare", False)))

    address_raw = merged.get("address") or merged.get("adresa")
    address_str = _format_address_str(address_raw)

    reg_com = normalize_text_value(
        merged.get("reg_com") or merged.get("reg_com_number") or merged.get("nrRegCom")
    )
    reg_status = normalize_text_value(
        merged.get("registration_status")
        or merged.get("onrc_status")
        or ("activ" if active else "inactiv")
    )

    result: dict[str, Any] = {
        "cui": norm_cui,
        "name": norm_name,
        "company_name": norm_name,
        "reg_com": reg_com or None,
        "address": address_str or address_raw,
        "active": active,
        "inactive": inactive,
        "inactive_since": merged.get("inactive_since"),
        "registration_status": reg_status,
        "vat_registered": vat_registered,
        "vat_since": merged.get("vat_since"),
        "vat_cancelled": merged.get("vat_cancelled"),
        "e_factura": e_factura,
        "split_vat": split_vat,
        "cash_vat": cash_vat,
        "source_mode": "simulated_fixture",
    }
    return result


def normalize_anaf_financials_payload(
    raw: Any, requested_cui: str, requested_year: int
) -> dict[str, Any] | None:
    """Extrage și normalizează situațiile financiare ANAF pentru `requested_year`.

    Returnează `None` dacă anul cerut nu se regăsește în fixture (pentru status `not_found`).
    Ridică `ValueError` dacă structura sau valorile numerice sunt malformate.
    """
    year_int = int(requested_year)
    year_str = str(year_int)

    # Role 1 stores the canonical fixture as a list with one object per year.
    # Convert only the requested row to the existing single-year shape.
    if isinstance(raw, list):
        matches = [
            item for item in raw
            if isinstance(item, dict)
            and int(item.get("year") or item.get("an") or 0) == year_int
        ]
        if not matches:
            return None
        if len(matches) != 1:
            raise ValueError(f"Mai multe înregistrări financiare pentru anul {year_int}.")
        raw = matches[0]

    if not isinstance(raw, dict):
        raise ValueError(
            "Răspunsul anaf_financials trebuie să fie un obiect sau o listă JSON."
        )

    norm_cui = normalize_cui(requested_cui or raw.get("cui"))

    year_payload: dict[str, Any] | None = None

    # Format 1: dicționar direct pentru un singur an {"cui": "...", "year": 2024, "turnover": 8100000}
    if "year" in raw or "an" in raw:
        file_year = int(raw.get("year") or raw.get("an"))
        if file_year == year_int:
            year_payload = raw
        else:
            return None
    # Format 2: sub-cheie "financials" sau "years" {"financials": {"2024": {...}, "2023": {...}}}
    elif isinstance(raw.get("financials"), dict):
        fin_map = raw["financials"]
        year_payload = fin_map.get(year_str) or fin_map.get(year_int)
        if year_payload is None:
            return None
    elif isinstance(raw.get("years"), dict):
        years_map = raw["years"]
        year_payload = years_map.get(year_str) or years_map.get(year_int)
        if year_payload is None:
            return None
    elif isinstance(raw.get("years"), list):
        for item in raw["years"]:
            if isinstance(item, dict) and int(item.get("year") or item.get("an") or 0) == year_int:
                year_payload = item
                break
        if year_payload is None:
            return None
    # Format 3: chei de ani direct la rădăcină {"2024": {...}, "2023": {...}}
    elif year_str in raw and isinstance(raw[year_str], dict):
        year_payload = raw[year_str]
    elif any(str(k).isdigit() and len(str(k)) == 4 for k in raw.keys()):
        return None
    # Format 4: dicționar plat fără cheie "year" dar cu indicatori financiari
    elif any(k in raw for k in ("turnover", "cifra_de_afaceri", "net_profit", "total_assets")):
        year_payload = raw
    else:
        raise ValueError("Structură anaf_financials nerecunoscută sau malformată.")

    if not isinstance(year_payload, dict):
        raise ValueError("Datele financiare pentru anul cerut sunt malformate.")

    turnover = _coerce_number(
        year_payload.get("turnover", year_payload.get("cifra_de_afaceri"))
    )
    if turnover is None:
        raise ValueError("Câmpul obligatoriu 'turnover' lipsește din anaf_financials.")

    financial_fields = (
        "total_revenue",
        "total_expenses",
        "net_profit",
        "fixed_assets",
        "current_assets",
        "total_assets",
        "equity",
        "liabilities",
        "employees",
    )

    normalized: dict[str, Any] = {
        "cui": norm_cui,
        "year": year_int,
        "turnover": turnover,
        "currency": str(year_payload.get("currency") or raw.get("currency") or "RON").upper(),
        "source_mode": "simulated_fixture",
    }

    for field_name in financial_fields:
        if field_name in year_payload and year_payload[field_name] is not None:
            normalized[field_name] = _coerce_number(year_payload[field_name])

    return normalized


def normalize_onrc_payload(raw: dict[str, Any], requested_cui: str) -> dict[str, Any]:
    """Normalizează datele de identitate, administratori și asociați din registrul simulat ONRC."""
    if not isinstance(raw, dict):
        raise ValueError("Răspunsul ONRC trebuie să fie un obiect JSON (dict).")

    comp = raw.get("company") if isinstance(raw.get("company"), dict) else {}
    people = raw.get("people") if isinstance(raw.get("people"), dict) else {}
    merged = {**comp, **people, **raw}

    norm_cui = normalize_cui(requested_cui or merged.get("cui"))
    raw_name = merged.get("name") or merged.get("company_name") or merged.get("denumire")
    if not raw_name or not str(raw_name).strip():
        raise ValueError("Câmpul 'name' / 'company_name' lipsește din răspunsul ONRC.")

    norm_name = normalize_company_name(str(raw_name))
    reg_com = normalize_text_value(
        merged.get("reg_com") or merged.get("reg_com_number") or merged.get("nr_reg_com")
    )
    legal_form = normalize_text_value(merged.get("legal_form") or "SRL").upper()
    onrc_status = normalize_text_value(
        merged.get("onrc_status") or merged.get("status") or "funcțiune"
    )

    raw_directors = merged.get("directors") or merged.get("administrators") or []
    if not isinstance(raw_directors, list):
        raise ValueError("Câmpul 'directors' din ONRC trebuie să fie o listă.")
    directors: list[dict[str, Any]] = []
    for d in raw_directors:
        if isinstance(d, str):
            directors.append(
                {
                    "name": normalize_person_name(d),
                    "role": "administrator",
                    "appointed": None,
                    "can_sign": True,
                }
            )
        elif isinstance(d, dict):
            directors.append(
                {
                    "name": normalize_person_name(d.get("name")),
                    "role": normalize_text_value(d.get("role") or "administrator"),
                    "appointed": d.get("appointed"),
                    "can_sign": bool(d.get("can_sign", True)),
                }
            )
        else:
            raise ValueError("Element invalid în lista 'directors' din ONRC.")

    raw_shareholders = merged.get("shareholders") or merged.get("associates") or []
    if not isinstance(raw_shareholders, list):
        raise ValueError("Câmpul 'shareholders' din ONRC trebuie să fie o listă.")
    shareholders: list[dict[str, Any]] = []
    for sh in raw_shareholders:
        if not isinstance(sh, dict):
            raise ValueError("Element invalid în lista 'shareholders' din ONRC.")
        shareholders.append(
            {
                "name": normalize_person_name(sh.get("name")),
                "type": normalize_text_value(sh.get("type") or "person"),
                "percent": _coerce_number(sh.get("percent", sh.get("share_percent"))),
            }
        )

    raw_ubos = merged.get("ubos") or []
    ubos: list[dict[str, Any]] = []
    if isinstance(raw_ubos, list):
        for u in raw_ubos:
            if isinstance(u, dict):
                ubos.append(
                    {
                        "name": normalize_person_name(u.get("name")),
                        "birth_date": u.get("birth_date"),
                        "nationality": u.get("nationality"),
                        "percent": _coerce_number(u.get("percent")),
                        "control": u.get("control"),
                    }
                )

    address_raw = merged.get("address")
    address_str = _format_address_str(address_raw)

    return {
        "cui": norm_cui,
        "name": norm_name,
        "company_name": norm_name,
        "legal_form": legal_form,
        "vat_prefix": bool(merged.get("vat_prefix", True)),
        "reg_com": reg_com,
        "reg_com_number": reg_com,
        "euid": normalize_text_value(merged.get("euid")) or None,
        "registration_date": merged.get("registration_date"),
        "caen": merged.get("caen"),
        "address": address_raw if isinstance(address_raw, dict) else address_str,
        "address_text": address_str,
        "status": onrc_status,
        "onrc_status": onrc_status,
        "share_capital_lei": _coerce_number(
            merged.get("share_capital_lei", merged.get("share_capital"))
        ),
        "directors": directors,
        "shareholders": shareholders,
        "ubos": ubos,
        "source_mode": "simulated_fixture",
    }


def normalize_court_cases_payload(
    raw: dict[str, Any] | list[Any], requested_cui: str
) -> dict[str, Any]:
    """Normalizează lista de dosare de instanță din registrul simulat de litigii."""
    norm_cui = normalize_cui(requested_cui)
    company_name = ""

    if isinstance(raw, list):
        raw_cases = raw
    elif isinstance(raw, dict):
        if not requested_cui and "cui" in raw and raw["cui"] is not None:
            norm_cui = normalize_cui(raw["cui"])
        company_name = normalize_company_name(
            raw.get("company_name") or raw.get("name")
        )
        if "cases" in raw:
            raw_cases = raw["cases"]
        elif "court_cases" in raw:
            raw_cases = raw["court_cases"]
        elif "dosare" in raw:
            raw_cases = raw["dosare"]
        else:
            raise ValueError("Răspunsul court_cases nu conține cheia 'cases' sau 'court_cases'.")
    else:
        raise ValueError("Răspunsul court_cases trebuie să fie dict sau list.")

    if not isinstance(raw_cases, list):
        raise ValueError("Lista de dosare din court_cases este malformată (nu este listă).")

    normalized_cases: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_cases):
        if not isinstance(item, dict):
            raise ValueError(f"Dosarul de la indexul {idx} din court_cases nu este un dict.")
        number = normalize_text_value(
            item.get("number") or item.get("case_number") or item.get("numar")
        )
        if not number:
            raise ValueError(f"Dosarul de la indexul {idx} nu are număr de dosar ('number').")

        category = normalize_text_value(item.get("category") or "other").lower()
        status = normalize_text_value(item.get("status") or "open").lower()
        subject = normalize_text_value(item.get("subject") or item.get("obiect"))

        normalized_cases.append(
            {
                "number": number,
                "case_number": number,
                "court": normalize_text_value(item.get("court") or item.get("instanta")),
                "subject": subject,
                "category": category,
                "party_role": normalize_text_value(item.get("party_role") or item.get("calitate")).lower(),
                "other_party": normalize_company_name(item.get("other_party"))
                if item.get("other_party")
                else None,
                "stage": normalize_text_value(item.get("stage") or item.get("stadiu")).lower(),
                "status": status,
                "registered": item.get("registered") or item.get("date"),
            }
        )

    open_cases = [c for c in normalized_cases if c["status"] == "open"]
    has_open_insolvency = any(
        c["category"] == "insolvency" or "insolven" in c["subject"].lower()
        for c in open_cases
    )
    has_open_enforcement = any(
        c["category"] == "enforcement" or "executare" in c["subject"].lower()
        for c in open_cases
    )

    return {
        "cui": norm_cui,
        "company_name": company_name or None,
        "cases": normalized_cases,
        "court_cases": normalized_cases,
        "total_cases": len(normalized_cases),
        "open_cases_count": len(open_cases),
        "has_open_insolvency": has_open_insolvency,
        "has_open_enforcement": has_open_enforcement,
        "source_mode": "simulated_fixture",
    }
