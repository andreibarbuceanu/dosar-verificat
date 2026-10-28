# Lovable Frontend / Sprint 1 Handoff

## Status

This branch contains a work-in-progress integration of the exported Lovable frontend with the
Sprint 1 FastAPI backend. The frontend build and unit tests pass. The complete browser-to-FastAPI
HTTP workflow has **not** been validated end to end and the integration must not yet be described
as complete.

Branch: `integration/frontend-sprint1`

## Implemented

- Imported the Lovable React/TypeScript/TanStack Start application under `web/`.
- Preserved the existing visual system, responsive layout, TanStack Router configuration,
  Tailwind styles, upload area, case queue, case-detail view, and evidence viewer layout.
- Added a typed FastAPI client in `web/src/lib/api/index.ts` using `VITE_API_BASE_URL`, defaulting
  to `http://localhost:8000`.
- Connected the case queue to `GET /cases`.
- Connected case details to `GET /cases/{id}` and `GET /cases/{id}/pipeline`.
- Replaced browser-only PDF classification in the main upload workflow with multipart upload to
  `POST /cases`, followed by processing through `POST /cases/{id}/run`.
- Connected evidence images to `GET /documents/{document_id}/pages/{page}`.
- Displayed backend document types, classification confidence/reason, verified extracted fields,
  page numbers, and exact supporting quotes.
- Added explicit error handling and an honest `Verification not yet available` state when the
  Sprint 1 pipeline returns `validation.status = "not_available"`.
- The UI no longer interprets an empty finding list as “all checks passed.”
- Added API and upload-component tests using mocked HTTP responses.
- Added the corrected npm lockfile (`web/package-lock.json`).

## Simulated data

The original JSON and PDF assets remain under `web/src/data/` and `web/public/pdfs/` for labeled
demo/testing use. Normal runtime code no longer imports `companies.json`, `intake_truth.json`,
`case_exceptions.json`, `expected`, or `planted_errors` to construct case statuses or findings.
The local TypeScript classifier is no longer authoritative in the upload workflow.

Seeded cases returned by FastAPI may still originate from backend fixtures. The frontend presents
them as backend responses and does not synthesize additional findings.

## API endpoints used

- `GET /cases`
- `POST /cases` with multipart field `files`
- `POST /cases/{id}/run`
- `GET /cases/{id}`
- `GET /cases/{id}/pipeline`
- `GET /documents/{document_id}/pages/{page}`

Sprint 1 returns classification and extraction results, but does not run per-case verification.
No Sprint 2 rules or registry functionality was introduced on this branch.

## Verification performed

From `web/`:

- `npm test`: **passed** — 3 test files, 7 tests.
- `npm run build`: **passed** — client, SSR, and Nitro bundles generated.
- `npx tsc --noEmit`: **failed** with two TypeScript diagnostics:
  - `src/lib/api/index.ts`: `VITE_API_BASE_URL` must be accessed with bracket notation under the
    current `noPropertyAccessFromIndexSignature` setting.
  - `src/lib/api/index.test.ts`: one mocked-call array access is considered possibly undefined.

The generated `web/.output/`, `web/node_modules/`, Nitro output, and other build artifacts are
ignored and are not part of the commit.

## Not yet validated

- A complete real browser → FastAPI upload → `/run` → detail-page workflow using DEMO-02.
- CORS behavior with both services running simultaneously on the teammate's machine.
- Evidence-page rendering after a real uploaded case completes.
- Backend failure/retry behavior beyond mocked frontend tests.
- Full backend regression tests during this handoff pass.
- Production deployment configuration. The current Vite/Nitro build uses the Lovable-provided
  Cloudflare preset and emits a non-blocking `vite-tsconfig-paths` migration warning.

## Known limitations

- The two standalone TypeScript diagnostics above should be fixed before requiring `tsc --noEmit`
  in CI, even though the Vite production build succeeds.
- The Sprint 1 API stores uploaded cases in memory and uploaded files under `storage/uploads/`.
- Seeded backend fixture documents do not necessarily have uploaded PDF bytes, so their page image
  endpoint can return 404; the UI displays an unavailable-evidence message.
- The frontend has no polling/progress endpoint; it waits for the synchronous `/run` request.
- `validation.status = "not_available"` is expected for Sprint 1 and must not be presented as a
  successful verification outcome.

## Run locally

Backend, from the repository root:

```bash
python3 -m pip install -r requirements.txt
LLM_BACKEND=replay python3 -m uvicorn app.api.main:app --reload
```

Frontend, in another terminal:

```bash
cd web
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

Quick checks:

```bash
cd web
npm test
npm run build
npx tsc --noEmit
```

## Recommended next steps

1. Fix the two narrow TypeScript diagnostics without changing runtime behavior.
2. Start FastAPI and Vite together and upload the real files from `pdfs/DEMO-02/` through the UI.
3. Confirm the backend, rather than frontend fixtures, supplies classifications and extracted
   fields, including the `12,400,000 RON` PDF turnover.
4. Confirm the UI clearly shows Sprint 1 verification as unavailable and does not fabricate R03.
5. Verify every evidence quote opens the corresponding uploaded document page.
6. Run the complete backend suite and re-run frontend tests/build after any corrections.
