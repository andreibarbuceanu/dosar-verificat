import type { DocType } from "@/lib/api";

export type { DocType } from "@/lib/api";

export const DOC_LABELS: Record<DocType, string> = {
  application: "Financing application",
  bilant: "Balance sheet",
  caf: "Tax clearance certificate",
  onrc: "ONRC registration certificate",
  ubo: "Beneficial owner declaration",
  unknown: "Unknown",
};

export const RULE_LABELS: Record<string, string> = {
  R01: "CUI check digit", R02: "Consistent identity across documents", R03: "Turnover vs. ANAF",
  R04: "Net profit vs. ANAF", R05: "Balance sheet equilibrium", R06: "Company active at ANAF",
  R07: "VAT history", R08: "Tax certificate age", R09: "Tax debts", R10: "Authorised signatory",
  R11: "Complete beneficial owners", R12: "EU/UN sanctions screening", R13: "Litigation and enforcement",
  R14: "Scanned, unreadable page", R15: "Hidden instruction in document",
};

export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return value.toLocaleString("ro-RO");
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(formatValue).join("; ");
  if (typeof value === "object") return Object.entries(value as Record<string, unknown>)
    .map(([key, item]) => `${key}: ${formatValue(item)}`).join(" · ");
  return String(value);
}
