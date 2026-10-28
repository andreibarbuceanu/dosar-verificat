import { createFileRoute, Link, useNavigate, useRouter } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AppHeader, StatusPill } from "@/components/AppHeader";
import { UploadIntake } from "@/components/UploadIntake";
import { listCases } from "@/lib/api";

const norm = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const control = "h-9 rounded-md border border-input bg-card px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

export const Route = createFileRoute("/")({
  loader: () => listCases(),
  head: () => ({ meta: [{ title: "Verified File — File queue" }] }),
  component: Index,
});

function Index() {
  const cases = Route.useLoaderData();
  const navigate = useNavigate();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("name-asc");
  const rows = useMemo(() => {
    const needle = norm(query.trim());
    const filtered = cases.filter((item) =>
      (!needle || norm(item.company_name || item.id).includes(needle) || item.id.toLowerCase().includes(needle)) &&
      (status === "all" || item.status === status));
    const direction = sort.endsWith("asc") ? 1 : -1;
    return [...filtered].sort((a, b) => direction * (a.company_name || a.id).localeCompare(b.company_name || b.id));
  }, [cases, query, status, sort]);

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-6xl space-y-6 px-6 py-10">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Credit files</h1>
          <p className="mt-1 text-muted-foreground">{cases.length} files loaded from the processing API</p>
        </div>
        <UploadIntake onComplete={async (caseId) => {
          await router.invalidate();
          await navigate({ to: "/cases/$id", params: { id: caseId } });
        }} />
        <div className="flex flex-wrap items-center gap-3">
          <select className={control} value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Status">
            <option value="all">All statuses</option><option value="new">Awaiting processing</option>
            <option value="running">Verification unavailable</option><option value="green">Completed</option>
            <option value="exceptions">Exceptions</option><option value="escalated">Escalated</option>
          </select>
          <select className={control} value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Sort">
            <option value="name-asc">Company A–Z</option><option value="name-desc">Company Z–A</option>
          </select>
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search company or case ID…" className={`${control} ml-auto w-full sm:w-72`} />
        </div>
        <section className="overflow-hidden rounded-md border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-secondary text-left text-xs uppercase tracking-wide text-secondary-foreground">
              <tr><th className="px-4 py-3">Company</th><th className="px-4 py-3">Findings</th><th className="px-4 py-3">Status</th></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.length === 0 && <tr><td colSpan={3} className="px-4 py-8 text-center text-muted-foreground">No files match.</td></tr>}
              {rows.map((item) => <tr key={item.id} className="transition-colors hover:bg-accent">
                <td className="px-4 py-3"><Link to="/cases/$id" params={{ id: item.id }} className="block">
                  <div className="font-medium">{item.company_name || "Company not extracted yet"}</div><div className="text-xs text-muted-foreground">{item.id}</div>
                </Link></td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{item.red} red · {item.amber} amber</td>
                <td className="px-4 py-3"><StatusPill status={item.status} /></td>
              </tr>)}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}
