# Full Branch Readiness Report

Date: 2026-07-20  
Branch: `agent/implement-weeks-3-4-copilot`

## Outcome

The final readiness gaps are closed across deterministic safety, immutable
auditing, append-only case history, evidence provenance, SKU conflict handling,
tenant-scoped discovery, maintenance search, and permission-aware UI behavior.

## Delivered behavior

- Deterministic viral/public-escalation phrases and direct-handoff intents
  (`health_safety`, `refund`, `complaint`, `damage`) always discard suggestions
  and require handoff. Model output can raise risk but cannot bypass these
  rules.
- Knowledge create/update/review, case create, suggestion edit, and every new
  outcome event emit immutable, recursively redacted audit events.
- Case list/detail responses include the complete ordered outcome timeline and
  derive each suggestion's latest adoption/rejection state from append-only
  events.
- Migration `0009_case_provenance` adds non-negative server response timing,
  citation source/retrieval timestamps, handoff reason, and complete conflict
  source IDs with safe historical defaults/backfills and a working downgrade.
- Explicit SKU codes in message bodies are matched as bounded literals against
  tenant-owned codes, merged after selected codes, deduplicated, and capped at
  three.
- `GET /api/v1/knowledge/items/search` is route-safe and restricted to
  maintenance roles, the active tenant, approved/unexpired narrative types,
  and the configured embedding model/version.
- `GET /api/v1/session` exposes the authenticated role and authoritative
  permission list. The knowledge UI hides create/edit/review controls from
  users without those permissions and displays all SKU conflict sources.
- The copilot UI uses persisted server timing and history, displays derived
  adoption state, and supports an idempotent suggestion rejection action whose
  key is retained across retries.

## TDD evidence

Focused RED states were observed before implementation:

- Safety: 9 failures for viral phrases and model/rule direct-handoff cases.
- Audit/timeline: missing audit rows, outcomes, and adoption state.
- Migration/provenance: missing `response_time_ms`,
  `source_updated_at`, `retrieved_at`, and migration columns.
- Evidence discovery: missing persisted conflict context, ignored body SKU
  codes, and `405` for the search route.
- Session/frontend: `404` session endpoint; absent historical timeline,
  rejection action, permission filtering, and conflict display.

The corresponding focused suites were rerun green after each implementation
slice.

## Final verification

- Backend: `266 passed in 46.85s`
- Frontend: `33 passed` across 4 Vitest files
- Ruff: `All checks passed!`
- mypy strict: `Success: no issues found in 55 source files`
- ESLint: passed
- Next.js production build: passed; all 8 static pages generated
- Alembic: `base -> head -> base -> head` passed, including migration `0009`
- `git diff --check`: passed
- `apps/web/next-env.d.ts`: unchanged

## Notes

Tenant RLS, existing API permission checks, immutable citation/outcome triggers,
and the external-action safety boundary remain unchanged. No `.superpowers`
artifacts are included.

## 2026-07-21 rereview addendum

The final security rereview findings are closed:

- Knowledge maintenance controls now fail closed while session permissions are
  loading, when the session request fails, and when permissions are malformed.
  A visible retry action recovers the permission request. Support remains
  read-only, while owner and implementer controls appear only after an
  authorized session succeeds.
- The migration `0009` contract is aligned across migration, ORM metadata, and
  response schemas. Citation provenance columns explicitly use timezone-aware
  SQLAlchemy types, case timing has the named non-negative check constraint in
  model metadata, and Pydantic rejects naive provenance timestamps and negative
  response timing.

Focused RED states were captured for permissive loading/error controls, missing
permission retry behavior, timezone-naive ORM metadata, and response schemas
accepting naive provenance. The corresponding focused tests are green.

Final rereview verification:

- Backend: `268 passed in 46.05s`
- Focused timezone/metadata schemas: `6 passed`
- Frontend: `37 passed` across 4 Vitest files
- Ruff: `All checks passed!`
- mypy strict: `Success: no issues found in 55 source files`
- ESLint: passed
- Next.js production build: passed; all 8 static pages generated
- Alembic: `base -> head -> base -> head` passed, including migration `0009`
