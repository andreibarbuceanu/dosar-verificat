import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { AppHeader, StatusPill } from "@/components/AppHeader";
import { ApiError, documentPageUrl, getCase, getPipeline, getVerification } from "@/lib/api";
import { DOC_LABELS, RULE_LABELS, formatValue } from "@/lib/intake";

export const Route = createFileRoute("/cases/$id")({
  loader: async ({ params }) => {
    try {
      const caseData = await getCase(params.id);
      const pipeline = await getPipeline(params.id).catch((error) => {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      });
      const verification = await getVerification(params.id).catch((error) => {
        if (error instanceof ApiError && (error.status === 409 || error.status === 404))
          return null;
        throw error;
      });
      return { caseData, pipeline, verification };
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) throw notFound();
      throw error;
    }
  },
  head: ({ loaderData }) => ({
    meta: [
      {
        title: `${loaderData?.caseData.company_name || loaderData?.caseData.id || "File"} — Verified File`,
      },
    ],
  }),
  component: CasePage,
});

function CasePage() {
  const { caseData: item, pipeline, verification } = Route.useLoaderData();
  const [selectedDocument, setSelectedDocument] = useState(0);
  const [selectedPage, setSelectedPage] = useState(1);
  const [pageUnavailable, setPageUnavailable] = useState(false);
  const document = item.documents[selectedDocument];
  const fields = useMemo(
    () => item.fields.filter((field) => field.doc_id === document?.id),
    [item.fields, document],
  );
  const classification = pipeline?.documents.find((result) => result.document_id === document?.id);
  const findings = item.outcome?.findings ?? pipeline?.validation.findings ?? [];

  function showEvidence(evidence: string[]) {
    const fieldId = evidence.find((ref) => ref.startsWith("field:"))?.slice("field:".length);
    const field = item.fields.find((candidate) => candidate.id === fieldId);
    if (!field) return;
    const index = item.documents.findIndex((candidate) => candidate.id === field.doc_id);
    if (index < 0) return;
    setSelectedDocument(index);
    setSelectedPage(field.page);
    setPageUnavailable(false);
  }

  useEffect(() => {
    setSelectedPage(1);
    setPageUnavailable(false);
  }, [selectedDocument]);

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">
          ← All files
        </Link>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {item.company_name || "Company not extracted"}
            </h1>
            <p className="text-sm text-muted-foreground">
              Case {item.id}
              {item.cui ? ` · CUI ${item.cui}` : ""}
            </p>
          </div>
          <StatusPill status={item.status} />
        </div>

        {pipeline?.validation.status === "not_available" && (
          <section className="rounded-md border border-warning/40 bg-warning/10 px-5 py-4">
            <h2 className="font-semibold">Verification not yet available</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {pipeline.validation.reason ||
                "Documents were classified and extracted, but no verification checks ran."}
            </p>
          </section>
        )}

        {verification && (
          <section className="rounded-md border border-border bg-card px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">Sprint 2 verification</h2>
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {verification.status.replaceAll("_", " ")}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {verification.doubles.length === 0
                ? "Registry, comparison and rules stages used the integrated backend."
                : `Fallback components: ${verification.doubles.join(", ")}.`}
            </p>
            {verification.errors.length > 0 && (
              <ul className="mt-2 text-sm text-destructive">
                {verification.errors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            )}
            {verification.not_checked.length > 0 && (
              <p className="mt-2 text-xs text-muted-foreground">
                Not checked: {verification.not_checked.map((finding) => finding.rule_id).join(", ")}
                . Unknown checks are not presented as passes.
              </p>
            )}
          </section>
        )}

        <section className="rounded-md border border-border bg-card">
          <div className="border-b border-border px-5 py-3 font-semibold">
            Checks returned by the backend
          </div>
          {findings.length === 0 ? (
            <p className="px-5 py-4 text-sm text-muted-foreground">
              No verification findings are available. This is not an “all checks passed” result.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {findings.map((finding) => (
                <li key={finding.id} className="flex gap-3 px-5 py-3 text-sm">
                  <span
                    className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${finding.result === "fail" ? "bg-destructive" : finding.result === "pass" ? "bg-success" : "bg-warning"}`}
                  />
                  <div>
                    <div className="font-semibold">
                      <span className="font-mono">{finding.rule_id}</span> ·{" "}
                      {RULE_LABELS[finding.rule_id] || finding.rule_id} ·{" "}
                      <span className="uppercase">{finding.result}</span>
                    </div>
                    <div className="text-muted-foreground">{finding.explanation}</div>
                    {finding.evidence.some((ref) => ref.startsWith("field:")) && (
                      <button
                        className="mt-1 text-xs font-semibold text-primary underline"
                        onClick={() => showEvidence(finding.evidence)}
                      >
                        View supporting page
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
          <nav className="space-y-2" aria-label="Documents">
            {item.documents.map((candidate, index) => (
              <button
                key={candidate.id}
                onClick={() => setSelectedDocument(index)}
                className={`w-full rounded-md border px-4 py-3 text-left transition-colors ${index === selectedDocument ? "border-ring bg-accent" : "border-border bg-card hover:bg-muted"}`}
              >
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <span className="flex h-5 w-5 items-center justify-center rounded-sm bg-primary font-mono text-[11px] text-primary-foreground">
                    {index + 1}
                  </span>
                  {DOC_LABELS[candidate.type]}
                </div>
                <div className="text-xs text-muted-foreground">
                  {candidate.file} · {candidate.pages} {candidate.pages === 1 ? "page" : "pages"}
                </div>
                {!candidate.readable && (
                  <span className="mt-1 inline-block rounded-sm bg-warning px-1.5 text-[10px] font-semibold text-warning-foreground">
                    UNREADABLE
                  </span>
                )}
              </button>
            ))}
          </nav>
          {document && (
            <div className="space-y-4">
              <section className="rounded-md border border-border bg-card p-5">
                <h2 className="font-semibold">Classification and extracted evidence</h2>
                {classification && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    Confidence {Math.round(classification.confidence * 100)}% ·{" "}
                    {classification.classification_reason}
                  </p>
                )}
                {fields.length === 0 ? (
                  <p className="mt-4 text-sm text-muted-foreground">
                    No verified fields were extracted.
                  </p>
                ) : (
                  <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                    {fields.map((field) => (
                      <div key={field.id} className="rounded-md bg-muted p-3">
                        <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {field.name}
                        </dt>
                        <dd className="mt-1 text-sm font-medium">{formatValue(field.value)}</dd>
                        <dd className="mt-2 text-xs text-muted-foreground">
                          Page {field.page}: “{field.quote}”
                        </dd>
                        <button
                          className="mt-2 text-xs font-semibold text-primary underline"
                          onClick={() => {
                            setSelectedPage(field.page);
                            setPageUnavailable(false);
                          }}
                        >
                          View evidence
                        </button>
                      </div>
                    ))}
                  </dl>
                )}
              </section>
              <section className="overflow-hidden rounded-md border border-border bg-card">
                <div className="flex items-center justify-between border-b border-border px-4 py-2 text-sm">
                  <span>Evidence page {selectedPage}</span>
                  <div className="flex gap-2">
                    <button
                      disabled={selectedPage <= 1}
                      onClick={() => {
                        setSelectedPage((page) => page - 1);
                        setPageUnavailable(false);
                      }}
                      className="rounded border px-2 disabled:opacity-40"
                    >
                      Previous
                    </button>
                    <button
                      disabled={selectedPage >= document.pages}
                      onClick={() => {
                        setSelectedPage((page) => page + 1);
                        setPageUnavailable(false);
                      }}
                      className="rounded border px-2 disabled:opacity-40"
                    >
                      Next
                    </button>
                  </div>
                </div>
                {pageUnavailable ? (
                  <p className="px-5 py-12 text-center text-sm text-muted-foreground">
                    The backend has no uploaded PDF content for this document, so the evidence page
                    cannot be displayed.
                  </p>
                ) : (
                  <img
                    key={`${document.id}-${selectedPage}`}
                    src={documentPageUrl(document.id, selectedPage)}
                    alt={`Page ${selectedPage} of ${document.file}`}
                    className="mx-auto max-h-[720px] w-auto"
                    onError={() => setPageUnavailable(true)}
                  />
                )}
              </section>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
