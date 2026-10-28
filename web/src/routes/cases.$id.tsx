import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { api, type Source } from "@/services/api";
import type { CaseSummary } from "@/lib/intake";
import { AppHeader } from "@/components/AppHeader";
import { DOC_LABELS, RULE_LABELS, getCase, pdfUrl } from "@/lib/intake";

export const Route = createFileRoute("/cases/$id")({
  loader: ({ params }) => {
    const c = getCase(params.id);
    return { id: params.id, name: c?.name ?? "" };
  },
  head: ({ loaderData }) => ({
    meta: [
      { title: `${loaderData?.id ?? "File"} · ${loaderData?.name ?? ""} — Verified File` },
      { name: "description", content: `Documents and checks for ${loaderData?.name ?? "file"}.` },
      { property: "og:title", content: `${loaderData?.name ?? "File"} — Verified File` },
      { property: "og:description", content: "Classified documents and R01–R15 rule checks." },
    ],
  }),
  component: CasePage,
});

function CasePage() {
  const { id } = Route.useParams();
  const [c, setC] = useState<CaseSummary | undefined | null>(null);
  const [source, setSource] = useState<Source>("mock");
  const [sel, setSel] = useState(0);
  useEffect(() => {
    setC(null);
    api.getCase(id).then((r) => { setC(r.data); setSource(r.source); });
  }, [id]);
  if (!c) {
    return (
      <div className="min-h-screen">
        <AppHeader />
        <main className="mx-auto max-w-6xl space-y-4 px-6 py-8">
          <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">← All files</Link>
          <p className="text-muted-foreground">{c === null ? "Loading file…" : "File not found."}</p>
        </main>
      </div>
    );
  }
  const doc = c.documents[sel];
  const fails = c.findings.filter((f) => f.result === "fail");

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">← All files</Link>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{c.name}</h1>
            <p className="text-sm text-muted-foreground">CUI {c.cui}{c.regCom && ` · ${c.regCom}`}{c.city && ` · ${c.city}`}</p>
            <p className="text-xs text-muted-foreground">{source === "backend" ? "Live data from backend" : "Backend offline · showing sample data"}</p>
          </div>
          <div className="flex items-center gap-3">
            {c.litigationScore !== undefined && (
              <span className="text-sm">Litigation score <b>{c.litigationScore}</b>/100</span>
            )}
          </div>
        </div>

        <section className="rounded-md border border-border bg-card">
          <div className="border-b border-border px-5 py-3 font-semibold">Checks</div>
          {fails.length === 0 ? (
            <p className={`px-5 py-4 text-sm font-medium ${c.status === "green" ? "text-success" : "text-muted-foreground"}`}>
              {c.status === "green" ? "All available checks passed. This file is Completed." : "No failed checks are available yet. This does not mean verification passed."}
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {fails.map((f) => (
                <li key={f.id} className="flex gap-3 px-5 py-3 text-sm">
                  <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${f.severity === "red" ? "bg-destructive" : "bg-warning"}`} />
                  <div>
                    <div className="font-semibold"><span className="font-mono">{f.rule_id}</span> · {RULE_LABELS[f.rule_id]}</div>
                    <div className="text-muted-foreground">{f.explanation}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
          <nav className="space-y-2">
            {c.documents.map((d, i) => (
              <button
                key={d.file}
                onClick={() => setSel(i)}
                className={`w-full rounded-md border px-4 py-3 text-left transition-colors ${i === sel ? "border-ring bg-accent" : "border-border bg-card hover:bg-muted"}`}
              >
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <span className="flex h-5 w-5 items-center justify-center rounded-sm bg-primary font-mono text-[11px] text-primary-foreground">{i + 1}</span>
                  {DOC_LABELS[d.doc_type]}
                </div>
                <div className="text-xs text-muted-foreground">{d.pages} {d.pages === 1 ? "page" : "pages"}</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {d.unreadable_pages.length > 0 && <span className="rounded-sm bg-warning px-1.5 text-[10px] font-semibold text-warning-foreground">SCANNED</span>}
                  {d.has_hidden_instruction && <span className="rounded-sm bg-destructive px-1.5 text-[10px] font-semibold text-destructive-foreground">INJECTION</span>}
                </div>
              </button>
            ))}
          </nav>

          {doc && (
            <div className="space-y-4">
              {doc.has_hidden_instruction && (
                <div className="rounded-sm bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  Hidden text trying to instruct the AI was detected. It was flagged and ignored.
                </div>
              )}
              <div className="overflow-hidden rounded-md border border-border bg-card">
                {doc.source === "backend" && doc.document_id ? (
                  <img
                    key={doc.document_id}
                    src={api.pageUrl(doc.document_id, 1)}
                    alt={`Page 1 of ${doc.file}`}
                    className="mx-auto max-h-[720px] w-auto"
                  />
                ) : (
                  <iframe key={doc.file} src={pdfUrl(doc.file)} title={doc.file} className="h-[640px] w-full" />
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

