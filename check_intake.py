"""Tester for Sprint 1 intake: PDF Processing, Classification, Extraction.

    python dataset/check_intake.py pdf      results.json
    python dataset/check_intake.py classify results.json
    python dataset/check_intake.py extract  results.json

Compares a results file with expected/intake_truth.json, prints the score and every
mistake, and writes dataset/results/<mode>-<time>.md. Last line: PASS or FAIL.
PASS needs a score of 100% by default; use --min-score 0.9 to accept less.
Formats: see INTAKE_OUTPUT.md. Standard library only.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
TRUTH_PATH = os.path.join(HERE, "expected", "intake_truth.json")
OUT_DIR = os.path.join(HERE, "results")
DOC_TYPES = ["application", "bilant", "caf", "onrc", "ubo", "unknown"]
HIDDEN_PHRASE = "ignore all previous"
MIN_TEXT_CHARS = 20


# ---------- normalizing ----------
def key_of(path):
    """'pdfs/EVAL-04/document_1.pdf' (any slashes, any prefix) -> 'EVAL-04/document_1.pdf'"""
    parts = str(path).replace("\\", "/").split("/")
    return "/".join(parts[-2:])


def squash(s):
    return re.sub(r"\s+", " ", str(s).replace(" ", " ")).strip()


def plain(s):
    """lower case, no diacritics, single spaces"""
    s = unicodedata.normalize("NFD", squash(s))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").casefold()


def to_number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return None
    s = re.sub(r"\s*(lei|ron)$", "", squash(v), flags=re.I).replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s):
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d+(,\d+)?", s):
        s = s.replace(",", ".")
    elif not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    return float(s)


def to_iso_date(v):
    if not isinstance(v, str):
        return None
    s = squash(v)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return s
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def equal(got, exp):
    """Value comparison: numbers as numbers, dates as dates, text without case/diacritics."""
    if isinstance(exp, dict):
        return isinstance(got, dict) and all(k in got and equal(got[k], exp[k]) for k in exp)
    if isinstance(exp, list):
        if not isinstance(got, list) or len(got) != len(exp):
            return False
        left = list(got)
        for e in exp:
            hit = next((i for i, g in enumerate(left) if equal(g, e)), None)
            if hit is None:
                return False
            left.pop(hit)
        return True
    if isinstance(exp, bool):
        return isinstance(got, bool) and got == exp
    if isinstance(exp, (int, float)):
        n = to_number(got)
        return n is not None and abs(n - exp) < 0.005
    if isinstance(exp, str):
        d = to_iso_date(exp)
        if d and to_iso_date(got):
            return to_iso_date(got) == d
        if isinstance(got, bool) or got is None or isinstance(got, (dict, list)):
            return False
        return plain(got) == plain(exp)
    return got == exp


def short(v, n=90):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= n else s[: n - 3] + "..."


# ---------- loading ----------
def load_truth():
    with open(TRUTH_PATH, encoding="utf-8") as f:
        return {key_of(t["file"]): t for t in json.load(f)}


def load_results(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("results", data.get("files", [data]))
    if not isinstance(data, list):
        sys.exit(f"{path}: expected a JSON list of results (see INTAKE_OUTPUT.md)")
    return {key_of(r["file"]): r for r in data if isinstance(r, dict) and "file" in r}


class Report:
    def __init__(self, mode):
        self.mode = mode
        self.mistakes = []  # (file, field, expected, got)
        self.lines = []     # summary text, shown on screen and in the .md file
        self.passed = False
        self.verdict = ""

    def miss(self, file, field, expected, got):
        self.mistakes.append((file, field, short(expected), short(got)))

    def say(self, text=""):
        self.lines.append(text)


# ---------- mode: pdf ----------
def check_pdf(truth, results, rep):
    ok_pages = bad_pages = 0
    for key, t in truth.items():
        r = results.get(key)
        if r is None:
            rep.miss(key, "result", "present", "missing")
            continue
        pages = {p.get("page"): p for p in r.get("pages", []) if isinstance(p, dict)}
        if len(r.get("pages", [])) != t["pages"]:
            rep.miss(key, "page count", t["pages"], len(r.get("pages", [])))
        printed_by_page = defaultdict(list)
        for f in t["fields"].values():
            if isinstance(f["printed"], str):
                printed_by_page[f["page"]].append(plain(f["printed"]))
        for n in range(1, t["pages"] + 1):
            p = pages.get(n)
            if p is None:
                continue
            want_readable = n not in t["unreadable_pages"]
            if bool(p.get("readable")) != want_readable:
                rep.miss(key, f"page {n} readable", want_readable, p.get("readable"))
                bad_pages += 1
                continue
            if want_readable:
                text = p.get("text") or ""
                found = len(text.strip()) >= MIN_TEXT_CHARS and (
                    not printed_by_page[n] or any(s in plain(text) for s in printed_by_page[n]))
                if not found:
                    rep.miss(key, f"page {n} text", "text with the page's content", short(text, 40) or "empty")
                    bad_pages += 1
                    continue
            ok_pages += 1
        if t["has_hidden_instruction"]:
            alltext = " ".join((p.get("text") or "") for p in pages.values())
            if HIDDEN_PHRASE not in plain(alltext):
                rep.miss(key, "hidden instruction text", f'"{HIDDEN_PHRASE}..." in the text', "not in the text")
    total = ok_pages + bad_pages
    files_ok = len(truth) - len({m[0] for m in rep.mistakes})
    rep.say(f"Files fully correct: {files_ok}/{len(truth)}")
    rep.say(f"Pages correct (count, readable flag, text found): {ok_pages}/{total}")
    unread = sum(len(t["unreadable_pages"]) for t in truth.values())
    rep.say(f"Unreadable (scanned) pages in the truth: {unread}")
    return files_ok / len(truth), f"{files_ok}/{len(truth)} files correct, {len(rep.mistakes)} mistakes"


# ---------- mode: classify ----------
def check_classify(truth, results, rep):
    conf = Counter()
    right = 0
    for key, t in truth.items():
        r = results.get(key)
        got = (r or {}).get("doc_type", "missing")
        got = got if got in DOC_TYPES else f"{got} (invalid)"
        c = (r or {}).get("confidence")
        if r is not None and not (isinstance(c, (int, float)) and not isinstance(c, bool) and 0 <= c <= 1):
            rep.miss(key, "confidence", "number 0-1", c)
        conf[(t["doc_type"], got)] += 1
        if got == t["doc_type"]:
            right += 1
        else:
            rep.miss(key, "doc_type", t["doc_type"], got)
    acc = right / len(truth)
    cols = DOC_TYPES + sorted({g for (_, g) in conf if g not in DOC_TYPES})
    rep.say(f"Accuracy: {right}/{len(truth)} = {acc:.1%}")
    inv = [k for k, t in truth.items() if t["doc_type"] == "unknown"]
    inv_ok = sum(1 for k in inv if (results.get(k) or {}).get("doc_type") == "unknown")
    rep.say(f"Invoice (must be unknown): {inv_ok}/{len(inv)}")
    rep.say("")
    rep.say("Confusion table (rows = truth, columns = got):")
    rep.say("")
    rep.say("| truth \\ got | " + " | ".join(cols) + " |")
    rep.say("| --- |" + " --- |" * len(cols))
    for row in DOC_TYPES:
        rep.say(f"| {row} | " + " | ".join(str(conf[(row, c)] or "") for c in cols) + " |")
    return acc, f"accuracy {acc:.1%} ({right}/{len(truth)}), invoice unknown {inv_ok}/{len(inv)}"


# ---------- mode: extract ----------
def quote_has(quote, printed):
    if not isinstance(quote, str):
        return False
    q = squash(quote).casefold()
    items = printed if isinstance(printed, list) else [printed]
    return all(squash(p).casefold() in q for p in items)


def check_extract(truth, results, rep):
    by_field = defaultdict(lambda: [0, 0])
    by_type = defaultdict(lambda: [0, 0])
    parts = Counter()
    n_fields = full = violations = 0
    hidden_ok = hidden_total = 0
    for key, t in truth.items():
        r = results.get(key)
        got_fields = (r or {}).get("fields") or {}
        if r is None:
            rep.miss(key, "result", "present", "missing")
        for name, f in t["fields"].items():
            n_fields += 1
            g = got_fields.get(name) if isinstance(got_fields.get(name), dict) else None
            ok = [False, False, False]
            if g is None:
                if r is not None:
                    rep.miss(key, name, "field extracted", "missing")
            else:
                ok[0] = equal(g.get("value"), f["value"])
                ok[1] = quote_has(g.get("quote"), f["printed"])
                ok[2] = g.get("page") == f["page"]
                if not ok[0]:
                    rep.miss(key, f"{name} value", f["value"], g.get("value"))
                if not ok[1]:
                    rep.miss(key, f"{name} quote", f"contains {f['printed']}", g.get("quote"))
                if not ok[2]:
                    rep.miss(key, f"{name} page", f["page"], g.get("page"))
            for label, v in zip(("value", "quote", "page"), ok):
                parts[label] += v
            good = all(ok)
            full += good
            by_field[name][0] += good
            by_field[name][1] += 1
            by_type[t["doc_type"]][0] += good
            by_type[t["doc_type"]][1] += 1
        for name in t["fields_on_unreadable_pages"]:
            g = got_fields.get(name)
            if isinstance(g, dict) and g.get("value") not in (None, "", []):
                violations += 1
                rep.miss(key, f"{name} (unreadable page)", "not extracted", g.get("value"))
        flagged = "hidden_instruction" in ((r or {}).get("flags") or [])
        if t["has_hidden_instruction"]:
            hidden_total += 1
            hidden_ok += flagged
            if not flagged:
                rep.miss(key, "flags", "hidden_instruction", (r or {}).get("flags") or [])
        elif flagged:
            rep.miss(key, "flags", "no flag", "hidden_instruction")
    unread_total = sum(len(t["fields_on_unreadable_pages"]) for t in truth.values())
    score = full / n_fields
    rep.say(f"Fields fully correct (value + quote + page): {full}/{n_fields} = {score:.1%}")
    rep.say(f"  value correct: {parts['value']}/{n_fields}   quote correct: {parts['quote']}/{n_fields}   page correct: {parts['page']}/{n_fields}")
    rep.say(f"Fields on unreadable pages wrongly extracted: {violations} (of {unread_total} that must stay empty)")
    rep.say(f"Hidden instruction flagged: {hidden_ok}/{hidden_total}")
    rep.say("")
    rep.say("Score per document type:")
    rep.say("")
    rep.say("| type | correct | total | score |")
    rep.say("| --- | --- | --- | --- |")
    for ty in DOC_TYPES:
        if ty in by_type:
            c, n = by_type[ty]
            rep.say(f"| {ty} | {c} | {n} | {c / n:.1%} |")
    rep.say("")
    rep.say("Score per field (all document types together):")
    rep.say("")
    rep.say("| field | correct | total | score |")
    rep.say("| --- | --- | --- | --- |")
    for name in sorted(by_field):
        c, n = by_field[name]
        rep.say(f"| {name} | {c} | {n} | {c / n:.1%} |")
    extra = len(rep.mistakes)
    return score, (f"{full}/{n_fields} fields correct ({score:.1%}), "
                   f"{violations} unreadable-page violations, hidden flagged {hidden_ok}/{hidden_total}, {extra} mistakes")


MODES = {"pdf": check_pdf, "classify": check_classify, "extract": check_extract}


# ---------- run ----------
def run(mode, results_path, min_score=1.0, write_report=True):
    truth = load_truth()
    results = load_results(results_path)
    rep = Report(mode)
    unknown_files = [k for k in results if k not in truth]
    if unknown_files:
        rep.say(f"Ignored {len(unknown_files)} result(s) for files not in the truth: {', '.join(unknown_files[:3])}")
    score, summary = MODES[mode](truth, results, rep)
    rep.passed = score >= min_score and not rep.mistakes if min_score >= 1.0 else score >= min_score and not _hard_failures(rep)
    rep.verdict = f"{'PASS' if rep.passed else 'FAIL'} {mode}: {summary}"
    text = render(rep, results_path, min_score)
    path = None
    if write_report:
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, f"{mode}-{datetime.now():%Y%m%d-%H%M%S}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return rep, text, path


def _hard_failures(rep):
    """Below 100% the safety checks still decide: unreadable page extracted, hidden instruction missed, invoice not unknown."""
    return [m for m in rep.mistakes if "(unreadable page)" in m[1] or m[1] == "flags" or
            (m[1] == "doc_type" and m[2] == "unknown") or m[1] == "result"]


def render(rep, results_path, min_score):
    out = [f"# Intake check: {rep.mode}", "",
           f"- Results file: `{os.path.basename(results_path)}`",
           f"- Time: {datetime.now():%Y-%m-%d %H:%M:%S}",
           f"- Pass rule: score >= {min_score:.0%}" + ("" if min_score >= 1.0 else " and no safety failure (unreadable page extracted, hidden instruction missed, invoice not unknown, file missing)"),
           "", f"**{rep.verdict}**", ""] + rep.lines + ["", f"## Mistakes ({len(rep.mistakes)})", ""]
    if rep.mistakes:
        out += ["| file | field | expected | got |", "| --- | --- | --- | --- |"]
        out += ["| " + " | ".join(c.replace("|", "\\|") for c in m) + " |" for m in rep.mistakes]
    else:
        out.append("None.")
    return "\n".join(out) + "\n"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=MODES)
    ap.add_argument("results", help="results.json from your part (format in INTAKE_OUTPUT.md)")
    ap.add_argument("--min-score", type=float, default=1.0, help="score needed for PASS, 0-1 (default 1.0 = perfect)")
    a = ap.parse_args()
    rep, text, path = run(a.mode, a.results, a.min_score)
    print("\n".join(rep.lines))
    print(f"\nMistakes ({len(rep.mistakes)}): file / field / expected / got")
    for m in rep.mistakes:
        print("  " + " / ".join(m))
    print(f"\nReport: {path}")
    print(rep.verdict)
    sys.exit(0 if rep.passed else 1)


if __name__ == "__main__":
    main()
