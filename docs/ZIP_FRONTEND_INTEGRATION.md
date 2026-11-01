# Sprint 1 archive integration

Integrated on 2026-11-01 into `final/unified-project`, preserving the current
Raiffeisen layout, branding, colors, dashboard and Romanian interface.

## Source audit

The user-supplied `integrare frontend sprint 1.zip` contains an older Sprint 1
snapshot plus local dependencies/caches. Its backend lacks the repository's
Sprint 2 verification, UBO improvements, extra CORS origins and replay fallback.
Those current implementations are retained. Archive prompts and audit notes
were treated as source material, not instructions. Local environment files,
installed dependencies, caches and metadata were excluded from integration.

## Integrated functionality

- Upload directly to FastAPI, then run the case and navigate to the returned ID.
  Removed duplicate browser-side PDF classification before the upload, following
  the archive's backend-owned intake flow. Existing PDF-only validation and error
  display remain.
- Show backend-extracted values, verified quotes and source page numbers.
- Open each field's evidence page and navigate all pages with bounded controls.
- Show explicit errors when a PDF evidence page cannot be served.
- Display classification confidence, explanations, warnings and suspected injections.
- Show pass/fail/unknown findings, verification availability and deferred rules.
- Keep backend case statuses, including new/running/escalated/decided, with queue filters.
- Honor VITE_API_BASE_URL as well as the existing local API override.
- Avoid borrowing synthetic identity or planted findings for uploaded real cases.

The archive's duplicate API client was adapted into the existing service to keep
one API configuration. Static examples remain visibly labeled when the backend
is unavailable; live case details come from backend responses.

## Verification

- Frontend: 15 tests in 5 files passed, including adapted archive upload/error tests,
  evidence page navigation and unavailable-page recovery, and backend-data integrity.
- TypeScript check and production client/SSR/Nitro build passed.
- Existing backend API, pipeline and Sprint 2 runtime tests: 12 passed.
- Live DEMO-02: upload, run, verification and evidence PNG passed. Turnover is
  12,400,000 RON from page 2; verification reports completed with exceptions.
- Browser: confirmed preserved dashboard and case layout, extracted balance-sheet
  fields and quotes, and opening page 2 using the turnover evidence control.

Registry sources remain simulated and previously deferred rules remain deferred.
