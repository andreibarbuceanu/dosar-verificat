"""Generate synthetic SME credit-file PDFs and the intake ground truth.

Input : companies.json (the truth: what ANAF, ONRC and the court portal would say)
Output: pdfs/<company_id>/document_<n>.pdf   (file names are shuffled so the classifier can't cheat)
        expected/intake_truth.json             (per PDF: document type, pages, every field with value, printed text and page)

Planted errors (companies.json -> planted_errors) change only the PDFs, never the truth.
Everything is fictitious. Every page carries a "synthetic document" footer.

Run:  pip install reportlab pymupdf
      python generate.py
"""
import copy
import json
import os
import random
import sys

import pymupdf
from reportlab.lib.colors import white, black, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
FOOTER = "DOCUMENT SINTETIC - DATE FICTIVE - NEXXT HACKATHON 2026 - FARA VALOARE JURIDICA"
W, H = A4

# ---------- fonts with Romanian diacritics ----------
FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]
for regular, bold in FONT_CANDIDATES:
    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("F", regular))
        pdfmetrics.registerFont(TTFont("FB", bold))
        break
else:
    sys.exit("No font with Romanian diacritics found (DejaVu Sans or Arial). Install one or edit FONT_CANDIDATES.")


# ---------- formatting ----------
def num(n):
    return f"{int(n):,}".replace(",", ".")


def dt(iso):
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def addr(a):
    return f"{a['street']} nr. {a['number']}, {a['city']}, jud. {a['county']}, cod poștal {a['postal_code']}"


# ---------- truth -> what the PDF shows (planted errors applied) ----------
def doc_view(c, doc_type):
    v = copy.deepcopy(c)
    for e in c["planted_errors"]:
        if e.get("document") != doc_type or "field" not in e:
            continue
        f, pv = e["field"], e.get("pdf_value")
        if doc_type == "application" and f == "cui" and pv == "WRONG_CHECK_DIGIT":
            cui = v["company"]["cui"]
            v["company"]["cui"] = cui[:-1] + str((int(cui[-1]) + 1) % 10)
        elif doc_type == "application" and f == "signed_by":
            v["credit_request"]["signed_by"] = pv
        elif doc_type == "bilant" and f == "turnover":
            v["financials"]["2024"]["turnover"] = pv
        elif doc_type == "bilant" and f == "net_profit":
            v["financials"]["2024"]["net_profit"] = pv
        elif doc_type == "bilant" and f == "total_assets":
            v["financials"]["2024"]["total_assets"] += e["pdf_value_delta"]
        elif doc_type == "caf" and f == "issue_date":
            v["tax_certificate"]["issue_date"] = pv
        elif doc_type == "ubo" and f == "ubos" and str(pv).startswith("REMOVE:"):
            name = pv.split(":", 1)[1]
            v["people"]["ubos"] = [u for u in v["people"]["ubos"] if u["name"] != name]
        elif doc_type == "onrc" and f == "address.number":
            v["company"]["address"]["number"] = pv
        else:
            sys.exit(f"Unknown planted error {e} for {c['id']}")
    return v


def effects(c, doc_type):
    return [e for e in c["planted_errors"] if e.get("document") == doc_type and "effect" in e]


# ---------- a tiny page writer that records where each field is printed ----------
class Doc:
    def __init__(self, path, title, subtitle=None):
        self.c = canvas.Canvas(path, pagesize=A4)
        self.c.setTitle(title)
        self.page = 1
        self.fields = {}
        self._header(title, subtitle)

    def _header(self, title, subtitle):
        self.y = H - 60
        self.c.setFont("FB", 14)
        self.c.drawString(50, self.y, title)
        self.y -= 18
        if subtitle:
            self.c.setFont("F", 9.5)
            self.c.drawString(50, self.y, subtitle)
            self.y -= 14
        self.c.setStrokeColor(HexColor("#888888"))
        self.c.line(50, self.y, W - 50, self.y)
        self.y -= 22

    def _footer(self):
        self.c.setFont("F", 7)
        self.c.setFillColor(HexColor("#777777"))
        self.c.drawString(50, 30, FOOTER)
        self.c.drawRightString(W - 50, 30, f"Pagina {self.page}")
        self.c.setFillColor(black)

    def new_page(self, title, subtitle=None):
        self._footer()
        self.c.showPage()
        self.page += 1
        self._header(title, subtitle)

    def section(self, text):
        self.y -= 6
        self.c.setFont("FB", 11)
        self.c.drawString(50, self.y, text)
        self.y -= 18

    def text(self, s, size=10):
        self.c.setFont("F", size)
        self.c.drawString(50, self.y, s)
        self.y -= 15

    def kv(self, label, printed, field=None, value=None):
        self.c.setFont("F", 10)
        self.c.drawString(50, self.y, f"{label}:")
        size = 10
        while size > 6 and pdfmetrics.stringWidth(printed, "FB", size) > W - 50 - 230:
            size -= 0.5
        self.c.setFont("FB", size)
        self.c.drawString(230, self.y, printed)
        self.y -= 17
        if field:
            self.fields[field] = {"value": value if value is not None else printed, "printed": printed, "page": self.page}

    def row(self, cells, xs, bold=False):
        self.c.setFont("FB" if bold else "F", 10)
        for cell, x in zip(cells, xs):
            if x < 0:
                self.c.drawRightString(-x, self.y, cell)
            else:
                self.c.drawString(x, self.y, cell)
        self.y -= 16

    def hidden(self, s):
        self.c.setFillColor(white)
        self.c.setFont("F", 4)
        self.c.drawString(52, 44, s)
        self.c.setFillColor(black)

    def save(self):
        self._footer()
        self.c.save()


# ---------- the five document types, plus an unrelated invoice ----------
def application(c, path):
    v = doc_view(c, "application")
    co, r = v["company"], v["credit_request"]
    d = Doc(path, "CERERE DE FINANȚARE - PERSOANE JURIDICE", "Către: BANCA DEMO S.A. (bancă fictivă), Direcția Clienți IMM")
    d.section("1. Date de identificare a solicitantului")
    d.kv("Denumire", co["name"], "company_name")
    d.kv("Cod unic de înregistrare (CUI)", co["cui"], "cui")
    d.kv("Nr. Registrul Comerțului", co["reg_com"], "reg_com_number")
    d.kv("Sediu social", addr(co["address"]), "address", co["address"])
    d.kv("Cod CAEN principal", co["caen"]["code"], "caen")
    d.kv("Reprezentant legal", r["signed_by"], "signed_by")
    d.section("2. Finanțarea solicitată")
    d.kv("Produs", r["product"], "product")
    d.kv("Suma solicitată", f"{num(r['amount'])} {r['currency']}", "requested_amount", r["amount"])
    d.kv("Durata", f"{r['term_months']} luni", "term_months", r["term_months"])
    d.kv("Scopul finanțării", r["purpose"], "purpose")
    coll = "; ".join(f"{g['type']} ({num(g['value'])} RON)" for g in r["collateral"]) or "fără"
    d.kv("Garanții propuse", coll, "collateral", r["collateral"])
    debts = "; ".join(f"{b['bank']}: {num(b['balance'])} RON" for b in r["existing_bank_debts"]) or "nu există"
    d.kv("Datorii bancare existente", debts, "existing_bank_debts", r["existing_bank_debts"])
    d.section("3. Declarație")
    d.text("Subsemnatul declar pe propria răspundere că informațiile din prezenta cerere sunt corecte și complete.")
    d.y -= 8
    d.kv("Data", dt(r["date"]), "request_date", r["date"])
    d.kv("Nume și semnătură", r["signed_by"])
    d.save()
    return d


def bilant(c, path):
    v = doc_view(c, "bilant")
    co, f24, f23 = v["company"], v["financials"]["2024"], v["financials"]["2023"]
    sub = f"Entitate: {co['name']}  |  CUI: {co['cui']}  |  Nr. Reg. Com.: {co['reg_com']}"
    d = Doc(path, "SITUAȚII FINANCIARE ANUALE - EXERCIȚIUL 2024", sub)
    d.fields["company_name"] = {"value": co["name"], "printed": co["name"], "page": 1}
    d.fields["cui"] = {"value": co["cui"], "printed": co["cui"], "page": 1}
    d.kv("Exercițiul financiar", "2024", "fiscal_year", 2024)
    d.kv("Adresa", addr(co["address"]))
    d.section("BILANȚ PRESCURTAT (sume în lei)")
    xs = [50, -400, -540]
    d.row(["Indicator", "31.12.2023", "31.12.2024"], xs, bold=True)
    for label, key in [("Active imobilizate", "fixed_assets"), ("Active circulante", "current_assets"),
                       ("TOTAL ACTIVE", "total_assets"), ("Capitaluri proprii", "equity"), ("Datorii", "liabilities")]:
        d.row([label, num(f23[key]), num(f24[key])], xs, bold=(key == "total_assets"))
        d.fields[key] = {"value": f24[key], "printed": num(f24[key]), "page": 1}
    d.new_page("CONTUL DE PROFIT ȘI PIERDERE - EXERCIȚIUL 2024", sub)
    d.section("Sume în lei")
    d.row(["Indicator", "2023", "2024"], xs, bold=True)
    for label, key in [("Cifra de afaceri netă", "turnover"), ("Venituri totale", "total_revenue"),
                       ("Cheltuieli totale", "total_expenses"), ("Profitul net al exercițiului", "net_profit"),
                       ("Număr mediu de salariați", "employees")]:
        d.row([label, num(f23[key]), num(f24[key])], xs)
        d.fields[key] = {"value": f24[key], "printed": num(f24[key]), "page": 2}
    d.y -= 10
    d.text("Administrator,")
    d.text(v["people"]["directors"][0]["name"])
    d.save()
    return d


def caf(c, path):
    v = doc_view(c, "caf")
    co, t = v["company"], v["tax_certificate"]
    d = Doc(path, f"CERTIFICAT DE ATESTARE FISCALĂ nr. {t['number']}",
            f"pentru persoane juridice, asociații, fundații și alte entități fără personalitate juridică  |  Emitent: {t['issued_by']}")
    d.fields["caf_number"] = {"value": t["number"], "printed": t["number"], "page": 1}
    d.kv("Contribuabil", co["name"], "company_name")
    d.kv("Cod de identificare fiscală", co["cui"], "cui")
    d.kv("Domiciliul fiscal", addr(co["address"]), "address", co["address"])
    d.kv("Data eliberării", dt(t["issue_date"]), "caf_issue_date", t["issue_date"])
    d.section("Obligații fiscale restante la data eliberării")
    if t["debts"]:
        for x in t["debts"]:
            d.row([x["type"], f"{num(x['amount'])} lei"], [60, -540])
        total = sum(x["amount"] for x in t["debts"])
        d.kv("Total obligații restante", f"{num(total)} lei", "caf_debts_total", total)
        d.kv("Situația contribuabilului", "înregistrează obligații fiscale restante", "caf_has_debts", True)
    else:
        d.kv("Total obligații restante", "0 lei", "caf_debts_total", 0)
        d.kv("Situația contribuabilului", "nu înregistrează obligații fiscale restante", "caf_has_debts", False)
    d.y -= 10
    d.text("Prezentul certificat s-a eliberat la cererea contribuabilului, pentru a servi la: instituție de credit.")
    d.text("Șef administrație,  (semnătură și ștampilă)")
    hidden = [e for e in effects(c, "caf") if e["effect"] == "hidden_instruction"]
    for e in hidden:
        d.hidden(e["text"])
    d.save()
    return d


def onrc(c, path):
    v = doc_view(c, "onrc")
    co, p = v["company"], v["people"]
    office = f"Oficiul Registrului Comerțului de pe lângă Tribunalul {co['address']['county']}"
    d = Doc(path, "CERTIFICAT CONSTATATOR", office)
    d.kv("Denumire", co["name"], "company_name")
    d.kv("Cod unic de înregistrare", co["cui"], "cui")
    d.kv("Număr de ordine în Registrul Comerțului", co["reg_com"], "reg_com_number")
    d.kv("EUID", co["euid"], "euid")
    d.kv("Data înregistrării", dt(co["registration_date"]), "registration_date", co["registration_date"])
    d.kv("Sediul social", addr(co["address"]), "address", co["address"])
    d.kv("Starea firmei", co["onrc_status"], "onrc_status")
    d.kv("Capital social subscris și vărsat", f"{num(co['share_capital_lei'])} lei", "share_capital", co["share_capital_lei"])
    d.kv("Activitate principală (CAEN)", f"{co['caen']['code']} - {co['caen']['description']}", "caen", co["caen"]["code"])
    d.new_page("CERTIFICAT CONSTATATOR (continuare)", office)
    d.section("Administratori / reprezentanți legali")
    for x in p["directors"]:
        d.row([x["name"], x["role"], f"numit la {dt(x['appointed'])}", "puteri depline"], [50, 230, 330, 450])
    d.fields["directors"] = {"value": p["directors"], "printed": [x["name"] for x in p["directors"]], "page": 2}
    d.section("Asociați")
    for x in p["shareholders"]:
        d.row([x["name"], "persoană fizică", f"{x['percent']}% din capitalul social"], [50, 230, 360])
    d.fields["shareholders"] = {"value": p["shareholders"], "printed": [f"{x['percent']}%" for x in p["shareholders"]], "page": 2}
    d.y -= 10
    d.text("Prezentul certificat constată situația firmei la data emiterii.")
    d.save()
    return d


def ubo(c, path):
    v = doc_view(c, "ubo")
    co, p, r = v["company"], v["people"], v["credit_request"]
    d = Doc(path, "DECLARAȚIE PRIVIND BENEFICIARUL REAL", "conform Legii nr. 129/2019 pentru prevenirea și combaterea spălării banilor")
    d.kv("Persoana juridică", co["name"], "company_name")
    d.kv("CUI", co["cui"], "cui")
    d.kv("Nr. Registrul Comerțului", co["reg_com"], "reg_com_number")
    d.section("Beneficiari reali")
    d.row(["Nume și prenume", "Data nașterii", "Cetățenie", "Deținere", "Modalitate"], [50, 220, 310, 380, 450], bold=True)
    for u in p["ubos"]:
        d.row([u["name"], dt(u["birth_date"]), u["nationality"], f"{u['percent']}%", u["control"]], [50, 220, 310, 380, 450])
    d.fields["ubos"] = {"value": p["ubos"], "printed": [u["name"] for u in p["ubos"]], "page": 1}
    d.y -= 10
    d.text("Declar pe propria răspundere că informațiile de mai sus sunt reale și complete.")
    d.kv("Data", dt(r["date"]), "declaration_date", r["date"])
    signer = p["directors"][0]["name"]
    d.kv("Administrator", signer, "signed_by")
    d.save()
    return d


def invoice(c, path):
    co = c["company"]
    d = Doc(path, "FACTURĂ FISCALĂ seria FCT nr. 0042", "Furnizor: HÂRTIA BUNĂ DISTRIBUȚIE SRL (firmă fictivă)")
    d.kv("Cumpărător", co["name"], "buyer")
    d.kv("CUI cumpărător", co["cui"])
    d.kv("Data facturii", "02.10.2026", "invoice_date", "2026-10-02")
    d.section("Produse")
    d.row(["Hârtie offset 80 g, 500 coli", "40 buc", "28,50 lei", "1.140,00 lei"], [50, 300, 380, 460])
    d.row(["Toner negru", "6 buc", "310,00 lei", "1.860,00 lei"], [50, 300, 380, 460])
    d.kv("Total de plată (cu TVA)", "3.570,00 lei", "total", 3570.00)
    d.save()
    return d


BUILDERS = {"application": application, "bilant": bilant, "caf": caf, "onrc": onrc, "ubo": ubo, "invoice": invoice}
EXPECTED_TYPE = {"application": "application", "bilant": "bilant", "caf": "caf", "onrc": "onrc", "ubo": "ubo", "invoice": "unknown"}


def make_scanned(path, page_no):
    """Replace one page with an image of itself: no text layer (R14)."""
    src = pymupdf.open(path)
    out = pymupdf.open()
    for i, page in enumerate(src):
        if i == page_no - 1:
            pix = page.get_pixmap(dpi=110)
            new = out.new_page(width=page.rect.width, height=page.rect.height)
            new.insert_image(new.rect, pixmap=pix)
        else:
            out.insert_pdf(src, from_page=i, to_page=i)
    src.close()
    out.save(path + ".tmp")
    out.close()
    os.replace(path + ".tmp", path)


def main():
    companies = json.load(open(os.path.join(HERE, "companies.json"), encoding="utf-8"))
    truth = []
    problems = []
    for c in companies:
        folder = os.path.join(HERE, "pdfs", c["id"])
        os.makedirs(folder, exist_ok=True)
        for old in os.listdir(folder):
            os.remove(os.path.join(folder, old))
        kinds = ["application", "bilant", "caf", "onrc", "ubo"] + [x["type"] for x in c.get("extra_documents", [])]
        random.Random(c["id"]).shuffle(kinds)
        for n, kind in enumerate(kinds, 1):
            name = f"document_{n}.pdf"
            path = os.path.join(folder, name)
            d = BUILDERS[kind](c, path)
            unreadable = []
            for e in effects(c, kind):
                if e["effect"] == "scanned":
                    make_scanned(path, e["page"])
                    unreadable.append(e["page"])
            # self-check: every printed value must be in the text of its page
            pdf = pymupdf.open(path)
            pages_text = [p.get_text() for p in pdf]
            pdf.close()
            readable_fields, lost_fields = {}, {}
            for fname, f in d.fields.items():
                if f["page"] in unreadable:
                    lost_fields[fname] = f
                    continue
                printed = f["printed"] if isinstance(f["printed"], list) else [f["printed"]]
                for s in printed:
                    if s not in pages_text[f["page"] - 1]:
                        problems.append(f"{c['id']}/{name} ({kind}): '{s}' not found on page {f['page']}")
                readable_fields[fname] = f
            truth.append({
                "company_id": c["id"], "file": f"pdfs/{c['id']}/{name}", "doc_type": EXPECTED_TYPE[kind],
                "pages": len(pages_text), "unreadable_pages": unreadable,
                "has_hidden_instruction": any(e["effect"] == "hidden_instruction" for e in effects(c, kind)),
                "planted_errors": [e["rule_id"] for e in c["planted_errors"] if e.get("document") == kind],
                "fields": readable_fields, "fields_on_unreadable_pages": lost_fields,
            })
            print(f"  {c['id']}/{name:16} {kind}")
    os.makedirs(os.path.join(HERE, "expected"), exist_ok=True)
    json.dump(truth, open(os.path.join(HERE, "expected", "intake_truth.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n{len(truth)} PDFs, truth in expected/intake_truth.json")
    if problems:
        print("\nSELF-CHECK FAILED:")
        print("\n".join(problems))
        sys.exit(1)
    print("Self-check passed: every expected value is printed on its page.")


if __name__ == "__main__":
    main()
