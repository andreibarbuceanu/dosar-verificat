export type CaseStatus = "new" | "running" | "green" | "exceptions" | "escalated" | "decided";
export type DocType = "application" | "bilant" | "caf" | "onrc" | "ubo" | "unknown";

export type CaseSummary = {
  id: string;
  company_name: string;
  status: CaseStatus;
  red: number;
  amber: number;
};
export type Document = {
  id: string;
  type: DocType;
  file: string;
  pages: number;
  readable: boolean;
};
export type EvidenceField = {
  id: string;
  name: string;
  value: unknown;
  doc_id: string;
  page: number;
  quote: string;
  verified: boolean;
};
export type Finding = {
  id: string;
  rule_id: string;
  severity: "red" | "amber" | "info";
  result: "pass" | "fail" | "unknown";
  evidence: string[];
  explanation: string;
  checker: "agree" | "disagree" | "n/a";
};
export type Case = {
  id: string;
  company_name: string;
  cui: string;
  status: CaseStatus;
  documents: Document[];
  fields: EvidenceField[];
  tool_results: unknown[];
  outcome: null | {
    case_id: string;
    result: "green" | "exceptions" | "escalated";
    litigation_score: number;
    deductions: unknown[];
    findings: Finding[];
  };
};
export type PipelineDocument = {
  document_id: string;
  file: string;
  pages: number;
  readable: boolean;
  document_type: DocType;
  confidence: number;
  classification_reason: string;
  fields: Array<Record<string, unknown>>;
  warnings: string[];
  error: string | null;
};
export type PipelineResult = {
  case_id: string;
  documents: PipelineDocument[];
  validation: { status: string; findings: Finding[]; reason?: string };
};
export type VerificationResult = {
  case_id: string;
  status: "completed" | "completed_with_errors" | "failed" | "not_available";
  stages: Record<string, "ok" | "error" | "skipped">;
  errors: string[];
  doubles: string[];
  findings: Finding[];
  not_checked: Finding[];
  rule_catalog: Array<{
    rule_id: string;
    description: string;
    implemented: boolean;
    mandatory: boolean;
  }>;
  litigation_score_status: "not_computed";
};

const configuredBase =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "http://localhost:8000";
export const API_BASE_URL = configuredBase.replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export const listCases = () => request<CaseSummary[]>("/cases");
export const getCase = (id: string) => request<Case>(`/cases/${encodeURIComponent(id)}`);
export const getPipeline = (id: string) =>
  request<PipelineResult>(`/cases/${encodeURIComponent(id)}/pipeline`);
export const getVerification = (id: string) =>
  request<VerificationResult>(`/cases/${encodeURIComponent(id)}/verification`);

export async function uploadCase(files: File[]): Promise<Case> {
  if (files.length === 0) throw new Error("Select at least one PDF.");
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  return request<Case>("/cases", { method: "POST", body });
}

export const runCase = (id: string) =>
  request<Case>(`/cases/${encodeURIComponent(id)}/run`, { method: "POST" });
export const documentPageUrl = (documentId: string, page: number) =>
  `${API_BASE_URL}/documents/${encodeURIComponent(documentId)}/pages/${page}`;
