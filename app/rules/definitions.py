"""Rule functions R01..R15 and the registry the engine dispatches on.

A rule reads its inputs and returns a Verdict. It never changes a value, never calls a
model and never reads the clock. Missing, unavailable, unverified, ambiguous or
conflicting evidence is "unknown", never "pass".
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from .helpers import (
    Context, Verdict, add_months, cui_control_digit, fmt_date, fmt_money, fmt_num, fmt_value,
    fold, parse_cui, problem_message, to_date, to_decimal, tool_label, unique,
)

_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def _up(text: str) -> str:
    """Capitalize the first letter only (keeps ANAF, ONRC as written)."""
    return text[:1].upper() + text[1:]


# ====================================================== comparison-consuming rules


@dataclass
class _Assessment:
    state: str                         # match | mismatch | unknown
    check_id: str
    refs: list[str] = field(default_factory=list)
    reason: str = ""
    left_src: str = ""
    right_src: str = ""
    left: object = None
    right: object = None
    diff: Decimal | None = None
    year: int | None = None
    currency: str | None = None


def _side_refs(side: object) -> list[str]:
    evidence = side.get("evidence") if isinstance(side, dict) else None
    if evidence is None:
        return []
    if isinstance(evidence, str):
        return [evidence]
    return [e for e in evidence if isinstance(e, str)]


def _source_of(ctx: Context, records: list[tuple[str, dict]]) -> str:
    kind, record = records[0]
    return ctx.field_source(record) if kind == "field" else tool_label(record)


def _assess(ctx: Context, comp: dict, *, check_year: bool, tolerance: Decimal | None,
            currency: str | None) -> _Assessment:
    """Can this comparison back a pass/fail? Checks its evidence against the real inputs."""
    check_id = str(comp.get("check_id") or "?")

    def unknown(reason: str) -> _Assessment:
        return _Assessment("unknown", check_id, reason=reason)

    if comp.get("status") not in ("match", "mismatch"):
        return unknown(f"comparația {check_id} nu a putut stabili rezultatul")

    refs: list[str] = []
    fields_used: list[tuple[str, dict]] = []
    tools_used: list[dict] = []
    per_side: dict[str, list[tuple[str, dict]]] = {}
    for name in ("left", "right"):
        side = comp.get(name) if isinstance(comp.get(name), dict) else {}
        side_refs = _side_refs(side)
        if not side_refs:
            return unknown(f"comparația {check_id} nu indică dovada pentru partea {name}")
        per_side[name] = []
        for ref in side_refs:
            found = ctx.resolve(ref)
            if found is None or found[0] not in ("field", "tool"):
                return unknown(f"dovada {ref} a comparației {check_id} nu există în dosar")
            kind, record = found
            if kind == "field":
                if record.get("verified") is not True:
                    return unknown(f"câmpul {ref} nu este verificat")
                fields_used.append((name, record))
            else:
                if record.get("status") != "ok":
                    return unknown(problem_message([record]))
                tools_used.append(record)
            refs.append(ref)
            per_side[name].append(found)

    left, right = comp["left"].get("value"), comp["right"].get("value")
    for name, record in fields_used:
        shown, stored = to_decimal(comp[name].get("value")), to_decimal(record.get("value"))
        if shown is not None and stored is not None and shown != stored:
            return unknown(f"comparația {check_id} nu corespunde valorii câmpului {record['id']}")

    year = None
    cur = None
    if check_year:
        tool = next((t for t in tools_used if t.get("tool") == "anaf_financials"), None)
        if tool is None:
            return unknown("lipsește dovada din registrul financiar")
        data = tool.get("data") or {}
        registry_years = {int(y) for y in ((tool.get("args") or {}).get("year"), data.get("year"))
                          if isinstance(y, (int, str)) and str(y).isdigit()}
        if len(registry_years) != 1:
            return unknown("anul din registru lipsește sau este contradictoriu")
        (year,) = registry_years
        doc_years = set()
        for _, record in fields_used:
            for fy in ctx.verified("fiscal_year"):
                if fy.get("doc_id") == record.get("doc_id") and str(fy.get("value")).isdigit():
                    doc_years.add(int(fy["value"]))
        doc_years |= {int(y) for y in _YEAR.findall(check_id)}
        if not doc_years:
            return unknown("anul fiscal al bilanțului nu a putut fi verificat")
        if doc_years != {year}:
            shown = ", ".join(str(y) for y in sorted(doc_years))
            return unknown(f"an diferit (bilanț {shown}, registru {year})")
        cur = data.get("currency")
        if cur and currency and cur != currency:
            return unknown(f"monedă diferită (registru {cur}, așteptat {currency})")
        cur = cur or currency

    diff = to_decimal(comp.get("difference"))
    if diff is None and to_decimal(left) is not None and to_decimal(right) is not None:
        diff = abs(to_decimal(left) - to_decimal(right))
    state = comp["status"]
    if state == "mismatch" and tolerance is not None and diff is not None and abs(diff) <= tolerance:
        state = "match"
    return _Assessment(
        state, check_id, refs=refs, left=left, right=right, diff=diff, year=year, currency=cur,
        left_src=_source_of(ctx, per_side["left"]), right_src=_source_of(ctx, per_side["right"]),
    )


def _consume(ctx: Context, rule_id: str, label: str, *, gate_tool: str | None = None,
             check_year: bool = False, money: bool = False,
             severity_of: Callable[[list[_Assessment]], str] | None = None) -> Verdict:
    """Roll up Role 3's comparisons for this rule: all match -> pass, any mismatch -> fail."""
    tolerance = to_decimal(ctx.th("tolerance_abs")) if money and "tolerance_abs" in ctx.rule_cfg["thresholds"] else None
    currency = ctx.th("currency") if money else None
    comps = [c for c in ctx.comparisons if c.get("rule_id") == rule_id]
    items = [_assess(ctx, c, check_year=check_year, tolerance=tolerance, currency=currency) for c in comps]

    def show(a: _Assessment, value: object) -> str:
        return fmt_value(value, (a.currency or currency) if money else None)

    def year(a: _Assessment) -> str:
        return f" {a.year}" if a.year else ""

    fails = [a for a in items if a.state == "mismatch"]
    if fails:
        parts = []
        for a in fails:
            diff = f"; diferență {fmt_money(a.diff, a.currency or currency)}" if money and a.diff is not None else ""
            parts.append(f"{a.left_src} indică {show(a, a.left)}, iar {a.right_src} indică {show(a, a.right)}{diff}")
        text = f"{label}{year(fails[0])}: " + " | ".join(parts) + "."
        severity = severity_of(fails) if severity_of else None
        return Verdict("fail", text, unique([r for a in fails for r in a.refs]), severity)

    matches = [a for a in items if a.state == "match"]
    unknowns = [a for a in items if a.state == "unknown"]
    if matches and not unknowns:
        parts = [f"{a.left_src} și {a.right_src} indică aceeași valoare ({show(a, a.left)})" for a in matches]
        text = f"{label}{year(matches[0])}: " + " | ".join(parts) + "."
        return Verdict("pass", text, unique([r for a in matches for r in a.refs]))

    reasons = [a.reason for a in unknowns]
    if not comps:
        reasons = [_missing_comparison_reason(ctx, rule_id, gate_tool)]
    return Verdict("unknown", f"{label}: nu poate fi stabilită ({'; '.join(unique(reasons))}).")


def _missing_comparison_reason(ctx: Context, rule_id: str, gate_tool: str | None) -> str:
    if gate_tool:
        tools = ctx.tools_named(gate_tool)
        if not tools:
            return f"sursa {gate_tool} nu a fost interogată"
        if not any(t.get("status") == "ok" for t in tools):
            return problem_message(tools)
    return f"comparația {rule_id} nu a fost furnizată de verificarea încrucișată"


def r02(ctx: Context) -> Verdict:
    markers = [fold(m) for m in ctx.th("cui_check_id_markers")]

    def severity(fails: list[_Assessment]) -> str:
        if any(any(fold(a.check_id).startswith(m) for m in markers) for a in fails):
            return ctx.rule_cfg["severity"]
        return ctx.th("non_cui_mismatch_severity")

    return _consume(ctx, "R02", "Identitatea firmei (CUI, denumire, nr. reg. com., adresă)",
                    severity_of=severity)


def r03(ctx: Context) -> Verdict:
    return _consume(ctx, "R03", "Cifra de afaceri", gate_tool="anaf_financials",
                    check_year=True, money=True)


def r04(ctx: Context) -> Verdict:
    return _consume(ctx, "R04", "Profitul net", gate_tool="anaf_financials",
                    check_year=True, money=True)


def r10(ctx: Context) -> Verdict:
    return _consume(ctx, "R10", "Administratorii din cerere față de ONRC", gate_tool="onrc_company")


def r11(ctx: Context) -> Verdict:
    return _consume(ctx, "R11", f"Beneficiarii reali declarați față de asociații cu cel puțin {fmt_num(ctx.th('min_percent'))}%",
                    gate_tool="onrc_company")


# ====================================================== single-source rules


def r01(ctx: Context) -> Verdict:
    found = ctx.verified("cui")
    if not found:
        return Verdict("unknown", "Niciun CUI verificat nu a fost extras din documente, cifra de control nu poate fi calculată.")
    bad, unreadable, good = [], [], []
    for f in found:
        cui = parse_cui(f.get("value"))
        if cui is None:
            unreadable.append(f)
        elif not 2 <= len(cui) <= 10 or cui_control_digit(cui) != int(cui[-1]):
            bad.append((f, cui))
        else:
            good.append((f, cui))
    if bad:
        parts = []
        for cui in unique([c for _, c in bad]):
            where = ", ".join(unique([ctx.field_source(f) for f, c in bad if c == cui]))
            if 2 <= len(cui) <= 10:
                detail = f"cifra de control ar trebui să fie {cui_control_digit(cui)}, nu {cui[-1]}"
            else:
                detail = f"lungimea de {len(cui)} cifre nu este validă"
            parts.append(f"CUI {cui} din {where} nu are cifră de control validă ({detail})")
        return Verdict("fail", "; ".join(parts) + ".", unique([f"field:{f['id']}" for f, _ in bad]))
    if unreadable:
        shown = ", ".join(str(f.get("value")) for f in unreadable)
        return Verdict("unknown", f"CUI-ul extras ({shown}) nu are un format numeric, cifra de control nu poate fi calculată.")
    cuis = sorted({cui for _, cui in good})
    return Verdict("pass", f"CUI {', '.join(cuis)} are cifra de control validă (cheia 753217532).",
                   unique([f"field:{f['id']}" for f, _ in good]))


def r05(ctx: Context) -> Verdict:
    names = ("total_assets", "equity", "liabilities")
    tolerance = to_decimal(ctx.th("tolerance_abs"))
    currency = ctx.th("currency")
    by_doc: dict[str, dict[str, list[dict]]] = {}
    for name in names:
        for f in ctx.verified(name):
            by_doc.setdefault(f["doc_id"], {}).setdefault(name, []).append(f)
    complete = {doc: g for doc, g in by_doc.items() if all(n in g for n in names)}
    if not complete:
        missing = [n for n in names if not any(n in g for g in by_doc.values())] or list(names)
        return Verdict("unknown", f"Echilibrul bilanțului nu poate fi verificat: lipsesc câmpuri verificate ({', '.join(missing)}) dintr-un același bilanț.")

    fails, unknowns, passes = [], [], []
    for doc, group in sorted(complete.items()):
        refs = [f"field:{f['id']}" for n in names for f in group[n]]
        if any(len({ctx.value_key(f['value']) for f in group[n]}) > 1 for n in names):
            unknowns.append(f"valori contradictorii în {ctx.doc_label(doc)}")
            continue
        total, equity, liabilities = (to_decimal(group[n][0]["value"]) for n in names)
        if None in (total, equity, liabilities):
            unknowns.append(f"valori nenumerice în {ctx.doc_label(doc)}")
            continue
        diff = abs(total - (equity + liabilities))
        sums = f"capitaluri proprii {fmt_money(equity, currency)} + datorii {fmt_money(liabilities, currency)} = {fmt_money(equity + liabilities, currency)}"
        if diff > tolerance:
            fails.append((f"în {ctx.doc_label(doc)} total active ({fmt_money(total, currency)}) nu este egal cu {sums}; diferență {fmt_money(diff, currency)}", refs))
        else:
            passes.append((f"în {ctx.doc_label(doc)} total active ({fmt_money(total, currency)}) este egal cu {sums}", refs))
    if fails:
        return Verdict("fail", "Bilanțul nu este echilibrat: " + "; ".join(t for t, _ in fails) + ".",
                       unique([r for _, refs in fails for r in refs]))
    if unknowns:
        return Verdict("unknown", "Echilibrul bilanțului nu poate fi verificat: " + "; ".join(unknowns) + ".")
    return Verdict("pass", "Bilanț echilibrat: " + "; ".join(t for t, _ in passes) + ".",
                   unique([r for _, refs in passes for r in refs]))


def _single_registry(ctx: Context, tool_name: str) -> tuple[dict | None, str | None]:
    """The one ok registry result for the company; None + reason if absent or conflicting."""
    tools, problem = ctx.usable_registry(tool_name)
    if problem:
        return None, problem
    if len(tools) > 1:
        return None, "răspunsuri multiple din registru pentru același CUI"
    return tools[0], None


def r06(ctx: Context) -> Verdict:
    tool, problem = _single_registry(ctx, "anaf_company")
    if problem:
        return Verdict("unknown", f"Starea firmei la ANAF nu poate fi verificată: {problem}.")
    data = tool["data"]
    if isinstance(data.get("active"), bool):
        active = data["active"]
    elif isinstance(data.get("inactive"), bool):
        active = not data["inactive"]
    else:
        return Verdict("unknown", f"Starea firmei la ANAF nu poate fi verificată: {tool_label(tool)} nu indică dacă firma este activă.")
    ref = (f"tool:{tool['id']}",)
    if active:
        return Verdict("pass", f"Firma figurează activă în {tool_label(tool)}.", ref)
    since = to_date(data.get("inactive_since"))
    when = f", din {fmt_date(since)}" if since else ""
    return Verdict("fail", f"Firma figurează inactivă în {tool_label(tool)}{when}.", ref)


def _application_date(ctx: Context):
    """The reference date for date rules: the application date in the file, never today."""
    field, problem = ctx.single_value("application_date")
    if problem:
        return None, None, problem
    parsed = to_date(field.get("value"))
    if parsed is None:
        return None, None, "data cererii nu poate fi citită"
    return field, parsed, None


def r07(ctx: Context) -> Verdict:
    app_field, applied, problem = _application_date(ctx)
    if problem:
        return Verdict("unknown", f"Anularea TVA nu poate fi verificată: {problem}.")
    tool, problem = _single_registry(ctx, "anaf_company")
    if problem:
        return Verdict("unknown", f"Anularea TVA nu poate fi verificată: {problem}.")
    months = int(ctx.th("window_months"))
    start = add_months(applied, -months)
    data = tool["data"]
    refs = (f"tool:{tool['id']}", f"field:{app_field['id']}")
    source = tool_label(tool)
    raw = data.get("vat_cancelled")
    if raw not in (None, False, ""):
        cancelled = to_date(raw)
        if cancelled is None:
            return Verdict("unknown", f"Data anulării TVA din {source} nu poate fi citită.")
        if cancelled > applied:
            return Verdict("unknown", f"Anularea TVA din {source} ({fmt_date(cancelled)}) este ulterioară datei cererii ({fmt_date(applied)}).")
        if cancelled >= start:
            return Verdict("fail", f"{source} arată anularea înregistrării în scopuri de TVA la {fmt_date(cancelled)}, în ultimele {months} luni față de data cererii {fmt_date(applied)}.", refs)
        return Verdict("pass", f"Anularea TVA din {source} ({fmt_date(cancelled)}) este mai veche de {months} luni față de data cererii {fmt_date(applied)}.", refs)
    since = to_date(data.get("vat_since"))
    if data.get("vat_registered") is True and since is not None and since <= start:
        return Verdict("pass", f"Firma este plătitoare de TVA fără întrerupere din {fmt_date(since)} ({source}); nicio anulare în ultimele {months} luni față de data cererii {fmt_date(applied)}.", refs)
    return Verdict("unknown", f"Anularea TVA nu poate fi stabilită: {source} nu indică o dată de anulare și nici o înregistrare continuă de peste {months} luni.")


def r08(ctx: Context) -> Verdict:
    app_field, applied, problem = _application_date(ctx)
    if problem:
        return Verdict("unknown", f"Vechimea certificatului fiscal nu poate fi verificată: {problem}.")
    caf, problem = ctx.single_value("caf_issue_date")
    if problem:
        return Verdict("unknown", f"Vechimea certificatului fiscal nu poate fi verificată: {problem}.")
    issued = to_date(caf.get("value"))
    if issued is None:
        return Verdict("unknown", "Vechimea certificatului fiscal nu poate fi verificată: data emiterii nu poate fi citită.")
    refs = (f"field:{caf['id']}", f"field:{app_field['id']}")
    age = (applied - issued).days
    if age < 0:
        return Verdict("unknown", f"Certificatul fiscal ({fmt_date(issued)}) este emis după data cererii ({fmt_date(applied)}), verificare manuală.", refs)
    limit = int(ctx.th("max_age_days"))
    if age > limit:
        return Verdict("fail", f"Certificatul fiscal emis la {fmt_date(issued)} are {age} zile față de data cererii {fmt_date(applied)} (maximum {limit} zile).", refs)
    return Verdict("pass", f"Certificatul fiscal emis la {fmt_date(issued)} are {age} zile față de data cererii {fmt_date(applied)} (maximum {limit} zile).", refs)


def r09(ctx: Context) -> Verdict:
    flag, problem = ctx.single_value("caf_has_debts")
    if problem:
        return Verdict("unknown", f"Datoriile din certificatul fiscal nu pot fi verificate: {problem}.")
    value = flag.get("value")
    if not isinstance(value, bool):
        return Verdict("unknown", "Datoriile din certificatul fiscal nu pot fi verificate: valoarea extrasă nu este da/nu.")
    refs = [f"field:{flag['id']}"]
    debt_field, _ = ctx.single_value("caf_total_debt")
    debt = to_decimal(debt_field.get("value")) if debt_field else None
    if debt_field is not None and debt is not None:
        refs.append(f"field:{debt_field['id']}")
    if value:
        amount = f" (total {fmt_money(debt)})" if debt is not None else ""
        return Verdict("fail", f"{_up(ctx.field_source(flag))} arată datorii la bugetul de stat{amount}.", unique(refs))
    if debt is not None and debt > 0:
        return Verdict("unknown", f"{_up(ctx.field_source(flag))} declară că nu are datorii, dar indică o datorie totală de {fmt_money(debt)}; verificare manuală.", unique(refs))
    return Verdict("pass", f"{_up(ctx.field_source(flag))} nu arată datorii.", unique(refs))


# ====================================================== R13 court cases

_FORMS = {"srl", "sa", "snc", "scs", "sca", "pfa", "ifn"}


def _split_name(name: str) -> tuple[str, str | None]:
    tokens = re.sub(r"[^a-z0-9]+", " ", fold(name).replace(".", "")).split()
    form = None
    if tokens[-2:] == ["srl", "d"]:
        form, tokens = "srl-d", tokens[:-2]
    elif tokens and tokens[-1] in _FORMS:
        form, tokens = tokens[-1], tokens[:-1]
    return " ".join(tokens), form


def _identity(ctx: Context, case: dict, cuis: set[str], names: list[str]) -> tuple[str, str]:
    """('certain'|'uncertain'|'other', reason). A case with no party data came from a CUI query."""
    case_cui = parse_cui(case.get("cui"))
    if case_cui is not None:
        return ("certain", "") if case_cui in cuis else ("other", "")
    party = case.get("party_name") or case.get("company_name")
    if not party:
        return "certain", ""
    if not names:
        return "uncertain", "denumirea firmei nu este disponibilă pentru comparație"
    core, form = _split_name(str(party))
    city = fold(case.get("party_city") or case.get("city"))
    address, _ = ctx.single_value("address")
    best = ("other", "")
    for name in names:
        n_core, n_form = _split_name(name)
        if core == n_core and form == n_form:
            if city and address and city not in fold(address.get("value")):
                found = ("uncertain", "oraș diferit")
            else:
                return "certain", ""
        elif core == n_core:
            found = ("uncertain", "formă juridică diferită")
        elif difflib.SequenceMatcher(None, core, n_core).ratio() >= float(ctx.th("name_similarity_min")):
            found = ("uncertain", "denumire asemănătoare")
        else:
            continue
        best = found
    return best


def r13(ctx: Context) -> Verdict:
    tools, problem = ctx.usable_registry("court_cases")
    if problem:
        reason = "portal instanțe indisponibil / date lipsă" if "indisponibil" in problem else problem
        return Verdict("unknown", f"Dosarele de instanță nu pot fi verificate: {reason}.")

    insolvency = [fold(k) for k in ctx.th("insolvency_keywords")]
    enforcement = [fold(k) for k in ctx.th("enforcement_keywords")]
    debtor_roles = {fold(r) for r in ctx.th("debtor_roles")}
    open_statuses = {fold(s) for s in ctx.th("open_statuses")}
    closed_statuses = {fold(s) for s in ctx.th("closed_statuses")}
    names = ctx.case_names()

    hard: dict[str, list[tuple[str, str, str]]] = {"insolvency": [], "enforcement": []}
    identity_doubt: list[tuple[str, str, str]] = []
    inconclusive: list[tuple[str, str, str]] = []
    analysed = 0
    for tool in tools:
        data = tool["data"]
        cases = data.get("cases", data.get("court_cases"))
        if not isinstance(cases, list):
            return Verdict("unknown", f"Dosarele de instanță nu pot fi verificate: răspunsul {tool_label(tool)} nu conține lista de dosare.")
        queried = {parse_cui((tool.get("args") or {}).get("cui") or data.get("cui"))} - {None}
        for case in cases:
            if not isinstance(case, dict):
                continue
            analysed += 1
            text = fold(f"{case.get('category', '')} {case.get('subject', '')}")
            kind = ("insolvency" if any(k in text for k in insolvency)
                    else "enforcement" if any(k in text for k in enforcement) else None)
            if kind is None:
                continue
            number = str(case.get("number") or case.get("case_number") or "?")
            identity, why = _identity(ctx, case, ctx.case_cuis() or queried, names)
            if identity == "other":
                continue
            entry = (number, tool["id"], why)
            if identity == "uncertain":
                identity_doubt.append(entry)
                continue
            status, role = fold(case.get("status")), fold(case.get("party_role"))
            if status in closed_statuses:
                continue
            if status not in open_statuses:
                inconclusive.append((number, tool["id"], "stare necunoscută"))
            elif not role:
                inconclusive.append((number, tool["id"], "rolul firmei necunoscut"))
            elif role in debtor_roles:
                court = case.get("court") or case.get("instanta")
                other = case.get("other_party") or case.get("counterparty")
                detail = f"dosar {number}" + (f" ({court})" if court else "")
                detail += ", firma este debitor" + (f", cealaltă parte: {other}" if other else "")
                hard[kind].append((number, tool["id"], detail))

    source = " / ".join(unique([tool_label(t) for t in tools]))
    fail_kind = "insolvency" if hard["insolvency"] else "enforcement" if hard["enforcement"] else None
    if fail_kind:
        shown = hard["insolvency"] + hard["enforcement"]
        extra = ""
        doubtful = identity_doubt + inconclusive
        if doubtful:
            extra = " Alte dosare de verificat de analist: " + ", ".join(n for n, _, _ in doubtful) + "."
        kind_ro = "insolvență" if fail_kind == "insolvency" else "executare silită"
        text = (f"{_up(source)} arată {kind_ro} deschisă împotriva firmei: "
                + "; ".join(d for _, _, d in shown) + f".{extra} Alertă de scenariu simulat, nu evaluare judiciară.")
        severity = ctx.th(f"{fail_kind}_severity")
        return Verdict("fail", text, unique([f"tool:{t}" for _, t, _ in shown]), severity)

    if identity_doubt or inconclusive:
        parts = []
        if identity_doubt:
            parts.append("posibilă potrivire, verificare analist: " + "; ".join(f"dosar {n} ({w})" for n, _, w in identity_doubt))
        if inconclusive:
            parts.append("date neconcludente: " + "; ".join(f"dosar {n} ({w})" for n, _, w in inconclusive))
        return Verdict("unknown", f"Dosarele din {source} nu permit o concluzie: " + " | ".join(parts) + ".")

    return Verdict("pass", f"{_up(source)} nu arată dosare deschise de insolvență sau executare silită în care firma este debitor ({analysed} dosare analizate).",
                   unique([f"tool:{t['id']}" for t in tools]))


# ====================================================== R14 documents


def r14(ctx: Context) -> Verdict:
    if not ctx.documents:
        return Verdict("unknown", "Lista documentelor încărcate nu este disponibilă, completitudinea dosarului nu poate fi verificată.")
    required = list(ctx.th("required_document_types"))
    docs = ctx.documents
    present = {d.get("type") for d in docs if d.get("readable") is True}
    missing = [t for t in required if t not in present and t not in {d.get("type") for d in docs}]
    unreadable = [d for d in docs if d.get("readable") is not True]
    problems = []
    if missing:
        problems.append("lipsesc documentele: " + ", ".join(missing))
    if unreadable:
        problems.append("nu pot fi citite (fără text): " + ", ".join(f"{d.get('file') or d['id']}" for d in unreadable))
    if problems:
        refs = [f"doc:{d['id']}" for d in (unreadable if unreadable else docs)]
        return Verdict("fail", "Dosarul nu este complet: " + "; ".join(problems) + ".", unique(refs))
    refs = [f"doc:{d['id']}" for d in docs if d.get("type") in required]
    return Verdict("pass", f"Toate cele {len(required)} tipuri de documente cerute sunt prezente și lizibile.", unique(refs))


REGISTRY: dict[str, Callable[[Context], Verdict]] = {
    "R01": r01, "R02": r02, "R03": r03, "R04": r04, "R05": r05, "R06": r06, "R07": r07,
    "R08": r08, "R09": r09, "R10": r10, "R11": r11, "R13": r13, "R14": r14,
}
