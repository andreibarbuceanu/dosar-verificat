import { useState } from "react";
import { DOC_LABELS, classifyText, extractPages, hasHiddenInstruction, type DocType } from "@/lib/intake";

type Result = {
  name: string;
  pages: number;
  unreadable: number[];
  type: DocType;
  confidence: number;
  hidden: boolean;
  error?: string;
};

export function UploadIntake() {
  const [results, setResults] = useState<Result[]>([]);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);

  async function handle(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    const out: Result[] = [];
    for (const f of Array.from(files)) {
      try {
        const pages = await extractPages(f);
        const text = pages.map((p) => p.text).join("\n");
        const c = classifyText(text);
        out.push({
          name: f.name,
          pages: pages.length,
          unreadable: pages.filter((p) => !p.readable).map((p) => p.page),
          type: c.type,
          confidence: c.confidence,
          hidden: hasHiddenInstruction(text),
        });
      } catch {
        out.push({ name: f.name, pages: 0, unreadable: [], type: "unknown", confidence: 0, hidden: false, error: "Invalid PDF" });
      }
    }
    setResults(out);
    setBusy(false);
  }

  return (
    <section className="rounded-md border border-border bg-card p-6">
      <h2 className="text-lg font-semibold">Upload documents</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Text is extracted page by page, then each PDF is classified automatically. Nothing leaves your browser.
      </p>
      <label
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files); }}
        className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed px-6 py-10 text-center transition-colors ${drag ? "border-ring bg-accent" : "border-border hover:bg-muted"}`}
      >
        <input type="file" accept="application/pdf" multiple className="sr-only" onChange={(e) => handle(e.target.files)} />
        <span className="grid h-12 w-12 place-items-center rounded-full bg-primary text-xl font-bold text-primary-foreground">↑</span>
        <span className="mt-3 font-medium">{busy ? "Processing…" : "Drop PDFs here or choose files"}</span>
        <span className="text-xs text-muted-foreground">Application, balance sheet, tax certificate, ONRC, UBO</span>
      </label>

      {results.length > 0 && (
        <ul className="mt-4 divide-y divide-border rounded-md border border-border">
          {results.map((r, i) => (
            <li key={i} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
              <div>
                <div className="font-medium">{r.name}</div>
                <div className="text-xs text-muted-foreground">
                  {r.error ?? `${r.pages} pages${r.unreadable.length ? ` · page(s) ${r.unreadable.join(", ")} unreadable` : ""}`}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {r.hidden && (
                  <span className="rounded-sm bg-destructive px-2 py-0.5 text-xs font-semibold text-destructive-foreground">
                    Hidden instruction
                  </span>
                )}
                <span className={`rounded-sm px-2 py-0.5 text-xs font-semibold ${r.type === "unknown" ? "bg-muted text-muted-foreground" : "bg-primary text-primary-foreground"}`}>
                  {DOC_LABELS[r.type]}
                </span>
                <span className="font-mono text-xs text-muted-foreground">{Math.round(r.confidence * 100)}%</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

