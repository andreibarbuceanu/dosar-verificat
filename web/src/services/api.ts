// FastAPI backend connector (Sprint 2 contract) with local mock fallback.
import { getCases as mockCases, getCase as mockCase, type CaseSummary } from "@/lib/intake";

export const DEFAULT_API_URL = "http://localhost:8000";
const KEY = "dv.apiUrl";

export function getApiUrl(): string {
  if (typeof window === "undefined") return DEFAULT_API_URL;
  return window.localStorage.getItem(KEY) || DEFAULT_API_URL;
}
export function setApiUrl(url: string) {
  window.localStorage.setItem(KEY, url.replace(/\/$/, ""));
}

export type Source = "backend" | "mixed" | "mock";
export type WithSource<T> = { data: T; source: Source };

export type ApiQueueItem = { id: string; company_name: string; status: string; red: number; amber: number };
export type ApiFinding = {
  id: string; rule_id: string; severity: "red" | "amber" | "info";
  result: "pass" | "fail" | "unknown"; evidence: string[]; explanation: string; checker?: string;
};
export type ApiCase = {
  id: string; company_name: string; cui: string; status: string;
  documents: { id: string; type: string; file: string; pages: number; readable: boolean }[];
  fields: { id: string; name: string; value: unknown; doc_id: string; page: number; quote: string; verified: boolean }[];
  tool_results: { id: string; tool: string; status: string; data: unknown; source?: string }[];
  outcome: { result: string; litigation_score: number; findings: ApiFinding[] } | null;
};
export type ApiVerification = {
  case_id: string; status: string; stages: Record<string, string>;
  errors: unknown[]; doubles: string[]; not_checked: ApiFinding[];
  rule_catalog: { rule_id: string; description: string; severity: string; implemented: boolean; mandatory: boolean }[];
  litigation_score_status: string;
};

async function req<T>(path: string, init?: RequestInit, timeoutMs = 4000): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(`${getApiUrl()}${path}`, { ...init, signal: ctrl.signal });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${await r.text().catch(() => "")}`);
    return (await r.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

/** Maps a backend case to the UI shape; missing docs/fields fall back to bundled data by CUI. */
function toSummary(c: ApiCase | ApiQueueItem): CaseSummary {
  const full = "cui" in c ? c : undefined;
  const mock = mockCases().find((m) => (full?.cui && m.cui === full.cui) || m.name === c.company_name);
  const result = full?.outcome?.result ?? c.status;
  return {
    id: c.id,
    set: mock?.set ?? "backend",
    name: c.company_name || mock?.name || c.id,
    cui: full?.cui || mock?.cui || "",
    regCom: mock?.regCom ?? "",
    city: mock?.city ?? "",
    status: result === "green" ? "green" : "exceptions",
    documents: mock?.documents ?? [],
    findings: full?.outcome ? full.outcome.findings.filter((f) => f.result === "fail") : mock?.findings ?? [],
    // Sprint 2: backend score is "not_computed" — never shown.
    litigationScore: undefined,
  };
}

export const api = {
  health: () => req<{ status: string }>("/health", undefined, 2000),

  async listCases(): Promise<WithSource<CaseSummary[]>> {
    try {
      const rows = await req<ApiQueueItem[]>("/cases");
      const backendRows = rows.map(toSummary);
      const backendIds = new Set(backendRows.map((row) => row.id));
      const bundledOnly = mockCases().filter((row) => !backendIds.has(row.id));
      return {
        data: [...backendRows, ...bundledOnly],
        source: bundledOnly.length > 0 ? "mixed" : "backend",
      };
    } catch {
      return { data: mockCases(), source: "mock" };
    }
  },

  async getCase(id: string): Promise<WithSource<CaseSummary | undefined>> {
    try {
      return { data: toSummary(await req<ApiCase>(`/cases/${id}`)), source: "backend" };
    } catch {
      return { data: mockCase(id), source: "mock" };
    }
  },

  getRawCase: (id: string) => req<ApiCase>(`/cases/${id}`),
  getVerification: (id: string) => req<ApiVerification>(`/cases/${id}/verification`),
  getPipeline: (id: string) => req<Record<string, unknown>>(`/cases/${id}/pipeline`),
  getAudit: (id: string) => req<unknown[]>(`/cases/${id}/audit`),

  createCase(files: File[]) {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return req<ApiCase>("/cases", { method: "POST", body: fd }, 30000);
  },
  runCase: (id: string) => req<ApiCase>(`/cases/${id}/run`, { method: "POST" }, 60000),
  decide: (findingId: string, decision: "accept" | "reject", note = "") =>
    req(`/findings/${findingId}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, note }),
    }),
  /** Still 501 in Sprint 2. */
  liveCheck: (body: unknown) =>
    req("/live-check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  pageUrl: (docId: string, n: number) => `${getApiUrl()}/documents/${docId}/pages/${n}`,
};

