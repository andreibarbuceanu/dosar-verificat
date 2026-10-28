import { createFileRoute, Link } from "@tanstack/react-router";
import { AppHeader, StatusPill } from "@/components/AppHeader";
import { useEffect, useMemo, useState } from "react";
import { api, type Source } from "@/services/api";
import { getCases } from "@/lib/intake";

const COUNTIES = ["Alba","Arad","Argeș","Bacău","Bihor","Bistrița-Năsăud","Botoșani","Brașov","Brăila","Buzău","Caraș-Severin","Călărași","Cluj","Constanța","Covasna","Dâmbovița","Dolj","Galați","Giurgiu","Gorj","Harghita","Hunedoara","Ialomița","Iași","Ilfov","Maramureș","Mehedinți","Mureș","Neamț","Olt","Prahova","Sălaj","Satu Mare","Sibiu","Suceava","Teleorman","Timiș","Tulcea","Vaslui","Vâlcea","Vrancea","București"];
const norm = (x: string) => x.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const sel = "h-9 rounded-md border border-input bg-card px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Verified File — File queue" },
      { name: "description", content: "Upload, classify and verify SME credit files in one place." },
      { property: "og:title", content: "Verified File — Smart Document Intake" },
      { property: "og:description", content: "Upload, classify and verify SME credit files." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Index,
});

function Index() {
  const [cases, setCases] = useState(getCases);
  const [source, setSource] = useState<Source | "loading">("loading");
  useEffect(() => {
    api.listCases().then((r) => { setCases(r.data); setSource(r.source); });
  }, []);
  const green = cases.filter((c) => c.status === "green").length;
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [county, setCounty] = useState("all");
  const [sort, setSort] = useState("name-asc");
  const rows = useMemo(() => {
    const nq = norm(q.trim());
    const r = cases.filter((c) =>
      (!nq || norm(c.name).includes(nq) || c.cui.includes(nq)) &&
      (status === "all" || c.status === status) &&
      (county === "all" || norm(c.city).endsWith(norm(county))));
    const [k, d] = sort.split("-");
    const m = d === "asc" ? 1 : -1;
    return [...r].sort((a, b) => m * (k === "name" ? a.name.localeCompare(b.name) : a.id.localeCompare(b.id, undefined, { numeric: true })));
  }, [cases, q, status, county, sort]);
  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-6xl space-y-6 px-6 py-10">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Credit files</h1>
          <p className="mt-1 text-muted-foreground">
            {cases.length} files · {green} Completed · {cases.length - green} Pending
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {source === "loading"
              ? "Connecting to backend…"
              : source === "backend"
                ? "Live data from backend"
                : source === "mixed"
                  ? "Live backend cases plus bundled demo files"
                  : "Backend offline · showing sample data"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select className={sel} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
            <option value="all">All statuses</option>
            <option value="green">Completed</option>
            <option value="exceptions">Pending</option>
          </select>
          <select className={sel} value={county} onChange={(e) => setCounty(e.target.value)} aria-label="County">
            <option value="all">All counties</option>
            {COUNTIES.map((x) => <option key={x} value={x}>{x}</option>)}
          </select>
          <select className={sel} value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
            <option value="name-asc">Company A–Z</option>
            <option value="name-desc">Company Z–A</option>
          </select>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search company or CUI…" className={`${sel} ml-auto w-full sm:w-72`} />
        </div>
        <div>
          <section className="overflow-hidden rounded-md border border-border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-secondary text-left text-xs uppercase tracking-wide text-secondary-foreground">
                <tr>
                                    <th className="px-4 py-3">Company</th>
                                    <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.length === 0 && (<tr><td colSpan={2} className="px-4 py-8 text-center text-muted-foreground">No files match.</td></tr>)}
                {rows.map((c) => {
                  return (
                    <tr key={c.id} className="transition-colors hover:bg-accent">
                      <td className="px-4 py-3">
                        <Link to="/cases/$id" params={{ id: c.id }} className="block">
                          <div className="font-medium">{c.name}</div>
                          <div className="text-xs text-muted-foreground">CUI {c.cui} · {c.city}</div>
                        </Link>
                      </td>
                      
                      <td className="px-4 py-3">
                        <StatusPill status={c.status} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        </div>
      </main>
    </div>
  );
}

