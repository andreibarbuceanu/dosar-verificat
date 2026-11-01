import { useRef, useState } from "react";
import { api, type ApiCase, type ApiPipeline } from "@/services/api";
import { formatValue } from "@/lib/intake";

const FIELD_LABELS: Record<string, string> = {
  company_name: "Denumire companie",
  cui: "CUI",
  reg_com_number: "Număr Registrul Comerțului",
  address: "Sediu social",
  application_date: "Data cererii",
  credit_product: "Produs de credit",
  requested_amount: "Suma solicitată",
  currency: "Monedă",
  term_months: "Durată în luni",
  credit_purpose: "Scopul creditului",
  collateral_value: "Valoarea garanțiilor",
  existing_bank_debt: "Datorii bancare existente",
  signed_by: "Semnatar",
  fiscal_year: "An fiscal",
  turnover: "Cifra de afaceri",
  total_revenue: "Venituri totale",
  total_expenses: "Cheltuieli totale",
  net_profit: "Profit net",
  fixed_assets: "Active imobilizate",
  current_assets: "Active circulante",
  total_assets: "Total active",
  equity: "Capitaluri proprii",
  liabilities: "Datorii",
  employees: "Număr mediu de salariați",
  caf_number: "Număr certificat fiscal",
  caf_issued_by: "Emitent certificat fiscal",
  caf_issue_date: "Data emiterii",
  caf_has_debts: "Există datorii fiscale",
  caf_total_debt: "Total datorii fiscale",
  euid: "EUID",
  legal_form: "Formă juridică",
  registration_date: "Data înregistrării",
  caen_code: "Cod CAEN",
  share_capital: "Capital social",
  onrc_status: "Starea societății",
  director: "Administrator",
  shareholder: "Asociat",
  ubo: "Beneficiar real",
};

export function DocumentEvidence({
  document,
  fields,
  classification,
}: {
  document: ApiCase["documents"][number];
  fields: ApiCase["fields"];
  classification?: ApiPipeline["documents"][number] | undefined;
}) {
  const viewer = useRef<HTMLElement>(null);
  const [page, setPage] = useState(1);
  const [unavailable, setUnavailable] = useState(false);
  function showPage(next: number) {
    setPage(next);
    setUnavailable(false);
  }
  function showEvidence(next: number) {
    showPage(next);
    viewer.current?.focus({ preventScroll: true });
    viewer.current?.scrollIntoView?.({ behavior: "auto", block: "start" });
  }
  return (
    <div className="space-y-4">
      <section className="rounded-md border border-border bg-card p-5">
        <h2 className="font-semibold">Clasificare și date extrase</h2>
        {classification && (
          <>
            <p className="mt-1 text-sm text-muted-foreground">
              Încredere {Math.round(classification.confidence * 100)}% ·{" "}
              {classification.classification_reason}
            </p>
            {classification.warnings.map((warning, index) => (
              <p key={index} className="mt-2 text-sm text-warning-foreground">
                {warning}
              </p>
            ))}
            {classification.injection_suspected.length > 0 && (
              <p role="alert" className="mt-2 text-sm text-destructive">
                Documentul conține instrucțiuni suspecte. Acestea nu sunt tratate ca instrucțiuni
                pentru verificare.
              </p>
            )}
            {classification.error && (
              <p role="alert" className="mt-2 text-sm text-destructive">
                {classification.error}
              </p>
            )}
          </>
        )}
        {fields.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Nu sunt disponibile câmpuri extrase pentru acest document.
          </p>
        ) : (
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            {fields.map((field) => (
              <div key={field.id} className="rounded-md bg-muted p-3">
                <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {FIELD_LABELS[field.name] ?? field.name}
                </dt>
                <dd className="mt-1 text-sm font-medium">{formatValue(field.value)}</dd>
                <dd className="mt-2 text-xs text-muted-foreground">
                  Pagina {field.page}: „{field.quote}” ·{" "}
                  {field.verified ? "Citat verificat" : "Citat neverificat"}
                </dd>
                <dd>
                  <button
                    className="mt-2 text-xs font-semibold text-foreground underline"
                    disabled={field.page < 1 || field.page > document.pages}
                    onClick={() => showEvidence(field.page)}
                  >
                    Vezi dovada
                  </button>
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>
      <section
        ref={viewer}
        tabIndex={-1}
        aria-label="Previzualizare dovadă PDF"
        className="scroll-mt-4 overflow-hidden rounded-md border border-border bg-card focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-2 text-sm">
          <span>
            Pagina {page} din {document.pages}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => showPage(page - 1)}
              className="rounded border px-2 disabled:opacity-40"
            >
              Anterior
            </button>
            <button
              disabled={page >= document.pages}
              onClick={() => showPage(page + 1)}
              className="rounded border px-2 disabled:opacity-40"
            >
              Următor
            </button>
          </div>
        </div>
        {unavailable || document.pages === 0 ? (
          <p role="status" className="px-5 py-12 text-center text-sm text-muted-foreground">
            Pagina nu este disponibilă. Backend-ul nu a putut furniza conținutul PDF.
          </p>
        ) : (
          <img
            key={`${document.id}-${page}`}
            src={api.pageUrl(document.id, page)}
            alt={`Pagina ${page} din ${document.file}`}
            className="mx-auto max-h-[720px] w-auto"
            onError={() => setUnavailable(true)}
          />
        )}
      </section>
    </div>
  );
}
