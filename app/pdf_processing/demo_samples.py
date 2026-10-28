from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

try:
    fitz: Any = importlib.import_module("fitz")
except ImportError:
    fitz = None


# JSON-ul de referință DEMO-02 folosit de toată echipa în Sprint 1
DEMO_02_GROUND_TRUTH: dict[str, Any] = {
    "id": "DEMO-02",
    "set": "demo",
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
    "anaf": {
        "active": True,
        "inactive_since": None,
        "vat_registered": True,
        "vat_since": "2019-10-01",
        "vat_cancelled": None,
        "e_factura": True,
        "split_vat": False,
        "cash_vat": False,
    },
    "financials": {
        "2024": {
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
    "tax_certificate": {
        "number": "CAF-12/58214",
        "issued_by": "AJFP Cluj",
        "issue_date": "2026-10-14",
        "has_debts": False,
        "debts": [],
    },
    "credit_request": {
        "date": "2026-10-20",
        "product": "credit de investiții",
        "amount": 1500000,
        "currency": "RON",
        "term_months": 60,
        "purpose": "Achiziție 3 autocamioane",
        "collateral": [{"type": "gaj pe vehicule", "value": 1800000}],
        "existing_bank_debts": [{"bank": "Bancă fictivă A", "balance": 900000}],
        "signed_by": "Andrei Mureșan",
    },
    "court_cases": [
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
    "sanctions_near_match": None,
    "planted_errors": [
        {
            "rule_id": "R03",
            "document": "bilant",
            "field": "turnover",
            "pdf_value": 12400000,
            "true_value": 8100000,
            "note": "Turnover inflated in the PDF; ANAF keeps the true value",
        }
    ],
    "expected": {
        "outcome": "exceptions",
        "rules": {"R03": "fail", "R13": "fail"},
        "all_other_rules": "pass",
    },
}


def _pdf_escape(text: str) -> str:
    """Escape pentru string-uri în PDF content stream."""
    ascii_map = str.maketrans(
        {
            "ă": "a",
            "Ă": "A",
            "â": "a",
            "Â": "A",
            "î": "i",
            "Î": "I",
            "ș": "s",
            "Ș": "S",
            "ş": "s",
            "Ş": "S",
            "ț": "t",
            "Ț": "T",
            "ţ": "t",
            "Ţ": "T",
        }
    )
    s = text.translate(ascii_map)
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_simple_pdf_bytes(
    pages_spec: list[dict[str, Any]],
) -> bytes:
    """Generează un fișier PDF 1.4 valid (fără dependențe externe sau cu fitz dacă există).

    Fiecare element din `pages_spec` poate avea:
    - `text`: str (textul vizibil de pe pagină)
    - `hidden_white_text`: str | None (text alb ascuns pentru testarea regulii R15)
    - `has_image_only`: bool (pagină scanată cu imagine bitmap fără text pentru testarea regulii R14)
    """
    if fitz is not None:
        doc = fitz.open()
        for spec in pages_spec:
            page = doc.new_page()
            text = spec.get("text") or ""
            if text:
                page.insert_text((50, 60), text, fontsize=11, color=(0, 0, 0))
            hidden = spec.get("hidden_white_text")
            if hidden:
                page.insert_text((50, 700), hidden, fontsize=10, color=(1, 1, 1))
            if spec.get("has_image_only"):
                pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 80), False)
                pix.clear_with(200)
                page.insert_image(fitz.Rect(50, 50, 250, 250), pixmap=pix)
        out_bytes = doc.tobytes()
        doc.close()
        return out_bytes

    # Builder PDF 1.4 nativ (compatibil 100% cu pypdf și orice viewer PDF)
    objects: list[bytes] = []

    def add_obj(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_obj_id = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    img_stream = b"\xcc" * (16 * 16 * 3)
    img_obj_id = add_obj(
        b"<< /Type /XObject /Subtype /Image /Width 16 /Height 16 "
        b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Length "
        + str(len(img_stream)).encode("ascii")
        + b" >>\nstream\n"
        + img_stream
        + b"\nendstream"
    )

    page_obj_ids: list[int] = []
    pages_root_placeholder_id = add_obj(b"")  # completat după

    for spec in pages_spec:
        lines_cmds: list[str] = []
        text = spec.get("text") or ""
        if text:
            lines_cmds.append("BT")
            lines_cmds.append("/F1 11 Tf")
            lines_cmds.append("0 0 0 rg")
            y = 770
            for raw_line in text.splitlines():
                escaped = _pdf_escape(raw_line)
                lines_cmds.append(f"1 0 0 1 50 {y} Tm ({escaped}) Tj")
                y -= 16
            lines_cmds.append("ET")

        hidden = spec.get("hidden_white_text")
        if hidden:
            escaped_h = _pdf_escape(hidden)
            lines_cmds.append(
                f"BT /F1 10 Tf 1 1 1 rg 1 0 0 1 50 40 Tm ({escaped_h}) Tj ET"
            )

        if spec.get("has_image_only"):
            lines_cmds.append("q 100 0 0 100 50 500 cm /Im1 Do Q")

        stream_bytes = "\n".join(lines_cmds).encode("latin-1")
        content_id = add_obj(
            b"<< /Length "
            + str(len(stream_bytes)).encode("ascii")
            + b" >>\nstream\n"
            + stream_bytes
            + b"\nendstream"
        )

        xobj_part = (
            f" /XObject << /Im1 {img_obj_id} 0 R >>".encode("ascii")
            if spec.get("has_image_only")
            else b""
        )
        page_id = add_obj(
            f"<< /Type /Page /Parent {pages_root_placeholder_id} 0 R "
            f"/MediaBox [0 0 595 842] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font_obj_id} 0 R >>".encode("ascii")
            + xobj_part
            + b" >> >>"
        )
        page_obj_ids.append(page_id)

    kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects[pages_root_placeholder_id - 1] = (
        f"<< /Type /Pages /Kids [{kids_str}] /Count {len(page_obj_ids)} >>".encode(
            "ascii"
        )
    )
    catalog_id = add_obj(
        f"<< /Type /Catalog /Pages {pages_root_placeholder_id} 0 R >>".encode("ascii")
    )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = [0]
    for i, obj_body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj_body)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)


def generate_demo_02_pdfs(output_dir: str | Path) -> dict[str, Path]:
    """Generează cele 5 PDF-uri pentru dosarul DEMO-02 (AGRO NORD TRANS SRL) conform JSON-ului comun."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    created: dict[str, Path] = {}

    # 1. Bilanț (2 pagini - pagina 2 conține exact citatul din Contractul Sprint 1 + eroarea plantată R03)
    bilant_path = out / "bilant_001.pdf"
    bilant_bytes = build_simple_pdf_bytes(
        [
            {
                "text": (
                    "MINISTERUL FINANTELOR - ANAF\n"
                    "SITUATII FINANCIARE ANUALE LA 31.12.2024\n"
                    "Formular F10 - Bilant prescurtat\n\n"
                    "Denumire entitate: AGRO NORD TRANS SRL\n"
                    "Forma juridica: SRL\n"
                    "CUI: RO41738203 (41738203)\n"
                    "Nr. Reg. Com.: J12/1834/2019\n"
                    "Adresa: Str. Fabricii nr. 47, Cluj-Napoca, Jud. Cluj, 400632\n"
                    "Cod CAEN: 4941 - Transporturi rutiere de marfuri\n\n"
                    "INDICATORI DIN BILANT 2024 (RON):\n"
                    "Active imobilizate: 3.100.000 lei\n"
                    "Active circulante: 1.900.000 lei\n"
                    "Total active: 5.000.000 lei\n"
                    "Capitaluri proprii: 1.450.000 lei\n"
                    "Datorii totale: 3.550.000 lei\n\n"
                    "INDICATORI DIN BILANT 2023 (RON):\n"
                    "Active imobilizate: 2.800.000 lei | Active circulante: 1.600.000 lei\n"
                    "Total active: 4.400.000 lei | Capitaluri proprii: 988.000 lei | Datorii: 3.412.000 lei"
                )
            },
            {
                "text": (
                    "Formular F20 - Contul de profit si pierdere (2024 vs 2023)\n"
                    "Entitate: AGRO NORD TRANS SRL (CUI 41738203)\n\n"
                    "EXERCITIUL FINANCIAR 2024:\n"
                    "Cifra de afaceri neta: 12.400.000 lei\n"
                    "Venituri totale: 8.240.000 lei\n"
                    "Cheltuieli totale: 7.690.000 lei\n"
                    "Profit net: 462.000 lei\n"
                    "Numar mediu de salariati: 34\n\n"
                    "EXERCITIUL FINANCIAR 2023:\n"
                    "Cifra de afaceri neta 2023: 7.350.000 lei\n"
                    "Venituri totale 2023: 7.420.000 lei\n"
                    "Cheltuieli totale 2023: 7.010.000 lei\n"
                    "Profit net 2023: 344.000 lei\n"
                    "Numar mediu de salariati 2023: 31\n\n"
                    "Administrator: Andrei Muresan"
                )
            },
        ]
    )
    bilant_path.write_bytes(bilant_bytes)
    created["bilant_001"] = bilant_path

    # 2. Certificat Constatator ONRC
    onrc_path = out / "onrc_001.pdf"
    onrc_bytes = build_simple_pdf_bytes(
        [
            {
                "text": (
                    "OFICIUL NATIONAL AL REGISTRULUI COMERTULUI\n"
                    "CERTIFICAT CONSTATATOR\n\n"
                    "Firma: AGRO NORD TRANS SRL\n"
                    "Forma juridica: SRL\n"
                    "Cod Unic de Inregistrare (CUI): 41738203 (Atribut fiscal RO)\n"
                    "Nr. de ordine in Registrul Comertului: J12/1834/2019\n"
                    "EUID: ROONRC.J12/1834/2019\n"
                    "Data inmatricularii: 2019-09-16\n"
                    "Stare firma: functiune\n"
                    "Activitate principala CAEN: 4941 - Transporturi rutiere de marfuri\n"
                    "Sediu social: Str. Fabricii nr. 47, Cluj-Napoca, Jud. Cluj, cod 400632\n"
                    "Capital social: 200 lei\n\n"
                    "ASOCIATI:\n"
                    "- Andrei Muresan (persoana fizica) - cota de participare: 60%\n"
                    "- Ioana Pop (persoana fizica) - cota de participare: 40%\n\n"
                    "ADMINISTRATORI / REPREZENTANTI LEGALI:\n"
                    "- Andrei Muresan - calitate: administrator, numit la 2019-09-16, drept de semnatura: DA"
                )
            }
        ]
    )
    onrc_path.write_bytes(onrc_bytes)
    created["onrc_001"] = onrc_path

    # 3. Certificat de Atestare Fiscală (CAF)
    caf_path = out / "caf_001.pdf"
    caf_bytes = build_simple_pdf_bytes(
        [
            {
                "text": (
                    "AGENTIA NATIONALA DE ADMINISTRARE FISCALA\n"
                    "Emitent: AJFP Cluj\n"
                    "CERTIFICAT DE ATESTARE FISCALA\n"
                    "Numar: CAF-12/58214\n"
                    "Data emiterii: 2026-10-14\n\n"
                    "Contribuabil: AGRO NORD TRANS SRL\n"
                    "CUI: 41738203 | Reg. Com.: J12/1834/2019\n"
                    "Domiciliu fiscal: Str. Fabricii nr. 47, Cluj-Napoca, Jud. Cluj, 400632\n\n"
                    "Situatia obligatiilor fiscale:\n"
                    "Are datorii fiscale restante: NU (0 RON)\n"
                    "Obligatii fiscale restante: 0 lei (fara datorii).\n"
                    "Prezentul certificat este valabil 30 de zile de la data emiterii."
                )
            }
        ]
    )
    caf_path.write_bytes(caf_bytes)
    created["caf_001"] = caf_path

    # 4. Cerere de credit
    app_path = out / "cerere_credit_001.pdf"
    app_bytes = build_simple_pdf_bytes(
        [
            {
                "text": (
                    "CERERE DE CREDIT IMM - RAIFFEISEN BANK\n"
                    "Data cererii: 2026-10-20\n\n"
                    "Solicitant: AGRO NORD TRANS SRL\n"
                    "CUI: 41738203 | Nr. Reg. Com.: J12/1834/2019\n"
                    "Adresa: Str. Fabricii nr. 47, Cluj-Napoca, Jud. Cluj, 400632\n\n"
                    "Produs solicitat: credit de investitii\n"
                    "Suma solicitata: 1.500.000 RON\n"
                    "Moneda: RON\n"
                    "Termen: 60 luni\n"
                    "Scopul creditului: Achizitie 3 autocamioane\n"
                    "Garantii propuse: gaj pe vehicule in valoare de 1.800.000 RON\n"
                    "Datorii bancare existente: Banca fictiva A - sold 900.000 RON\n\n"
                    "Semnat de: Andrei Muresan"
                )
            }
        ]
    )
    app_path.write_bytes(app_bytes)
    created["cerere_credit_001"] = app_path

    # 5. Declarație Beneficiari Reali (UBO)
    ubo_path = out / "ubo_001.pdf"
    ubo_bytes = build_simple_pdf_bytes(
        [
            {
                "text": (
                    "DECLARATIE PRIVIND BENEFICIARII REALI (UBO)\n\n"
                    "Subsemnatul Andrei Muresan, in calitate de administrator al:\n"
                    "Denumire societate: AGRO NORD TRANS SRL\n"
                    "CUI: 41738203 | Nr. Reg. Com.: J12/1834/2019\n"
                    "Adresa: Str. Fabricii nr. 47, Cluj-Napoca, Jud. Cluj, 400632\n\n"
                    "Declar pe propria raspundere urmatorii beneficiari reali:\n"
                    "1. Andrei Muresan - data nasterii: 1984-03-12, cetatenie: RO, cota: 60%, control: direct\n"
                    "2. Ioana Pop - data nasterii: 1987-11-02, cetatenie: RO, cota: 40%, control: direct\n\n"
                    "Semnatura: Andrei Muresan"
                )
            }
        ]
    )
    ubo_path.write_bytes(ubo_bytes)
    created["ubo_001"] = ubo_path

    return created
