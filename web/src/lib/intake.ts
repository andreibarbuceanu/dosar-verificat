import companiesRaw from "@/data/companies.json";
import truthRaw from "@/data/intake_truth.json";
import demo02Raw from "@/data/case_exceptions.json";
import indicatorsRaw from "@/data/ind.json";

export type DocType = "application" | "bilant" | "caf" | "onrc" | "ubo" | "unknown";

export const DOC_LABELS: Record<DocType, string> = {
  application: "Cerere de finanțare",
  bilant: "Bilanț contabil",
  caf: "Certificat de atestare fiscală",
  onrc: "Certificat constatator ONRC",
  ubo: "Declarație privind beneficiarul real",
  unknown: "Document necunoscut",
};

export const RULE_LABELS: Record<string, string> = {
  R01: "Verificarea cifrei de control CUI",
  R02: "Identitate consecventă în toate documentele",
  R03: "Cifra de afaceri comparată cu ANAF",
  R04: "Profitul net comparat cu ANAF",
  R05: "Echilibrul bilanțului contabil",
  R06: "Societate activă la ANAF",
  R07: "Istoricul TVA",
  R08: "Vechimea certificatului fiscal",
  R09: "Datorii fiscale",
  R10: "Semnatar autorizat",
  R11: "Beneficiari reali declarați complet",
  R12: "Verificare sancțiuni UE/ONU",
  R13: "Litigii și executări silite",
  R14: "Pagină scanată, fără text lizibil",
  R15: "Instrucțiune ascunsă în document",
};

export type TruthField = { value: unknown; printed: unknown; page: number };
export type TruthDoc = {
  document_id?: string;
  source?: "backend";
  company_id: string;
  file: string;
  doc_type: DocType;
  pages: number;
  unreadable_pages: number[];
  has_hidden_instruction: boolean;
  planted_errors: { rule_id: string; note?: string }[];
  fields: Record<string, TruthField>;
  fields_on_unreadable_pages: Record<string, TruthField>;
};

export type Finding = {
  id: string;
  rule_id: string;
  severity: "red" | "amber" | "info";
  result: "pass" | "fail" | "unknown";
  explanation: string;
};

type Company = {
  id: string;
  set: string;
  company: { name: string; cui: string; reg_com: string; address: { city: string; county: string } };
  credit_request?: { amount?: number; requested_amount?: number; purpose?: string };
  planted_errors: { rule_id: string; note?: string; document?: string }[];
  expected: { outcome: "green" | "exceptions"; rules_failing?: string[] };
};

const companies = companiesRaw as unknown as Company[];
const truth = truthRaw as unknown as TruthDoc[];

export type CaseSummary = {
  id: string;
  set: string;
  name: string;
  cui: string;
  regCom: string;
  city: string;
  status: "green" | "exceptions";
  documents: TruthDoc[];
  findings: Finding[];
  litigationScore?: number | undefined;
};

const SEVERITY: Record<string, "red" | "amber"> = {
  R05: "amber", R07: "amber", R08: "amber", R14: "amber",
};

function buildFindings(c: Company): Finding[] {
  if (c.id === "DEMO-02") return (demo02Raw as any).outcome.findings as Finding[];
  const failing = new Set([...(c.expected.rules_failing ?? []), ...c.planted_errors.map((p) => p.rule_id)]);
  return [...failing].sort().map((rid) => ({
    id: `${c.id}-${rid}`,
    rule_id: rid,
    severity: SEVERITY[rid] ?? "red",
    result: "fail",
    explanation: c.planted_errors.find((p) => p.rule_id === rid)?.note ?? "The rule failed verification.",
  }));
}

export function getCases(): CaseSummary[] {
  return companies.map((c) => ({
    id: c.id,
    set: c.set,
    name: c.company.name,
    cui: c.company.cui,
    regCom: c.company.reg_com,
    city: `${c.company.address.city}, ${c.company.address.county}`,
    status: c.expected.outcome,
    documents: truth.filter((t) => t.company_id === c.id),
    findings: buildFindings(c),
    litigationScore: c.id === "DEMO-02" ? (demo02Raw as any).outcome.litigation_score : undefined,
  }));
}

export function getCase(id: string) {
  return getCases().find((c) => c.id === id);
}

export const pdfUrl = (file: string) => `/${file}`;

export function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return v >= 1900 && v <= 2100 && Number.isInteger(v) ? String(v) : v.toLocaleString("ro-RO");
  if (typeof v === "boolean") return v ? "da" : "nu";
  if (typeof v === "string") return v;
  if (Array.isArray(v))
    return v
      .map((x) =>
        typeof x === "object" && x
          ? Object.values(x as Record<string, unknown>).filter((y) => typeof y !== "boolean").join(" · ")
          : String(x),
      )
      .join("; ");
  if (typeof v === "object") return Object.values(v as Record<string, unknown>).join(", ");
  return String(v);
}

// ---------- Classifier (port of app/agents/classifier) ----------
const INDICATORS = indicatorsRaw as unknown as Record<string, [string, number][]>;
const MIN_SCORE = 6;
const MIN_DISTINCT = 2;
const AMBIGUITY = 0.72;

export function normalizeText(t: string) {
  return t
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export function classifyText(text: string): { type: DocType; confidence: number; matches: string[] } {
  const norm = normalizeText(text);
  if (!norm) return { type: "unknown", confidence: 0, matches: [] };
  const padded = ` ${norm} `;
  const ranking = Object.entries(INDICATORS)
    .map(([cat, inds]) => {
      const matched: string[] = [];
      let score = 0;
      for (const [phrase, w] of [...inds].sort((a, b) => b[0].length - a[0].length)) {
        if (padded.includes(` ${phrase} `) && !matched.some((m) => m.includes(phrase))) {
          matched.push(phrase);
          score += w;
        }
      }
      return { cat, score, matched };
    })
    .sort((a, b) => b.score - a.score);
  const best = ranking[0]!;
  const second = ranking[1]!;
  if (best.score < MIN_SCORE || best.matched.length < MIN_DISTINCT)
    return { type: "unknown", confidence: Math.round(Math.min(0.49, best.score / 15) * 100) / 100, matches: best.matched };
  if (second.score >= MIN_SCORE && second.score / best.score >= AMBIGUITY)
    return { type: "unknown", confidence: 0.5, matches: best.matched };
  const evidence = Math.min(best.score / 15, 1);
  const separation = Math.max(0, (best.score - second.score) / best.score);
  const diversity = Math.min(best.matched.length / 4, 1);
  const conf = Math.min(0.99, 0.45 + 0.3 * evidence + 0.15 * separation + 0.1 * diversity);
  return { type: best.cat as DocType, confidence: Math.round(conf * 100) / 100, matches: best.matched };
}

const INJECTION = /(ignore (all )?(previous|prior) (rules|instructions)|system note|approve this file|mark every check|ignor[ăa] (toate )?(regulile|instruc))/i;
export const hasHiddenInstruction = (text: string) => INJECTION.test(text);

// ---------- PDF text extraction (browser only) ----------
export type PageText = { page: number; text: string; readable: boolean };

export async function extractPages(file: File | ArrayBuffer): Promise<PageText[]> {
  const pdfjs = await import("pdfjs-dist");
  const worker = (await import("pdfjs-dist/build/pdf.worker.min.mjs?url")).default;
  pdfjs.GlobalWorkerOptions.workerSrc = worker;
  const data = file instanceof ArrayBuffer ? file : await file.arrayBuffer();
  const doc = await pdfjs.getDocument({ data }).promise;
  const out: PageText[] = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const tc = await page.getTextContent();
    const text = tc.items.map((it: any) => ("str" in it ? it.str : "")).join(" ").replace(/\s+/g, " ").trim();
    out.push({ page: i, text, readable: text.length > 0 });
  }
  return out;
}

