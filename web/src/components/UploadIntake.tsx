import { useState } from "react";
import { runCase, uploadCase } from "@/lib/api";

export function UploadIntake({ onComplete }: { onComplete: (caseId: string) => void | Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handle(files: FileList | null) {
    if (!files?.length || busy) return;
    setBusy(true);
    setError(null);
    try {
      const selected = Array.from(files);
      const invalid = selected.find((file) => !file.name.toLowerCase().endsWith(".pdf"));
      if (invalid) throw new Error(`${invalid.name}: only PDF files are accepted.`);
      const created = await uploadCase(selected);
      await runCase(created.id);
      await onComplete(created.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The documents could not be processed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-md border border-border bg-card p-6">
      <h2 className="text-lg font-semibold">Upload documents</h2>
      <p className="mt-1 text-sm text-muted-foreground">PDFs are uploaded to FastAPI for classification and evidence extraction.</p>
      <label
        onDragOver={(event) => { event.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(event) => { event.preventDefault(); setDrag(false); void handle(event.dataTransfer.files); }}
        className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed px-6 py-10 text-center transition-colors ${drag ? "border-ring bg-accent" : "border-border hover:bg-muted"}`}
      >
        <input type="file" accept="application/pdf,.pdf" multiple disabled={busy} className="sr-only" onChange={(event) => void handle(event.target.files)} />
        <span className="grid h-12 w-12 place-items-center rounded-full bg-primary text-xl font-bold text-primary-foreground">↑</span>
        <span className="mt-3 font-medium">{busy ? "Uploading and processing…" : "Drop PDFs here or choose files"}</span>
        <span className="text-xs text-muted-foreground">Application, balance sheet, tax certificate, ONRC, UBO</span>
      </label>
      {error && <p role="alert" className="mt-4 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
    </section>
  );
}
