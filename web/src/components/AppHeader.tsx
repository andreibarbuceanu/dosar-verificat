import mark from "@/assets/raiffeisen-mark.png.asset.json";
import { Link } from "@tanstack/react-router";

export function AppHeader() {
  return (
    <header className="bg-primary text-primary-foreground">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link to="/" className="flex items-center gap-3">
          <img src={mark.url} alt="" aria-hidden="true" className="h-9 w-auto" />
          <span className="flex items-center gap-3" style={{ fontFamily: "'Source Sans 3', sans-serif" }}>
            <span className="text-2xl font-bold tracking-tight">Raiffeisen Bank</span>
            <span className="h-6 w-px bg-primary-foreground/60" aria-hidden="true" />
            <span className="text-lg font-semibold">Make it happen</span>
          </span>
        </Link>
      </div>
    </header>
  );
}

export function StatusPill({ status }: { status: string }) {
  if (status === "green" || status === "decided") return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-success/15 px-2.5 py-0.5 text-xs font-semibold text-success">
      <span className="h-1.5 w-1.5 rounded-full bg-success" /> Completed
    </span>
  );
  if (status === "exceptions" || status === "escalated") return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-destructive/10 px-2.5 py-0.5 text-xs font-semibold text-destructive">
      <span className="h-1.5 w-1.5 rounded-full bg-destructive" /> Pending
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-warning/15 px-2.5 py-0.5 text-xs font-semibold text-warning-foreground">
      <span className="h-1.5 w-1.5 rounded-full bg-warning" /> {status === "new" ? "Awaiting processing" : "Verification pending"}
    </span>
  );
}
