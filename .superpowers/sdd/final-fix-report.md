# Final branch review remediation report

Date: 2026-07-20

## Scope and hashes

- Binding brief: `.superpowers/sdd/final-fix-brief.md`
- Starting commit: `d87be91b19f454130d3cf5117104162145a9b0d2`
- Remediation implementation commit: `a0f0c1a2b734e81e55998fa7e942d330d1b0e778`
- Branch: `agent/implement-weeks-3-4-copilot`

## RED/GREEN evidence

All behavior changes were driven by focused tests before the corresponding
implementation.

| Slice | RED evidence | GREEN evidence |
| --- | --- | --- |
| Multilingual PII and residual fail-closed handling | 17 focused failures covering address, WeChat, customer name, QQ, Alipay, structured keys, persisted/provider leakage, and unlabelled `wxid` | `18 passed, 60 deselected` |
| Severe deterministic safety | Severe English/Chinese medical phrases initially failed to classify and skip the provider | Included in `18 passed, 60 deselected`; provider non-invocation asserted |
| Required fresh SKU and factual validation | 12 failures for no-SKU output, structured/prose price, origin, inventory and weight contradictions, and evaluation mismatches | `12 passed, 31 deselected` |
| Embedding injection/version and timezone safety | 5 failures for production provider behavior, metadata, aware/future timestamps, and expiry boundary | `6 passed, 16 deselected` after implementation |
| Migration invariants | 7 failures for cross-tenant ownership, invalid case/citation enums, and migration catalog/round-trip expectations | `7 passed` |
| Knowledge lifecycle UI | Create timestamp and lifecycle edit expectations failed before UI conversion/full edit support | `8 passed` in `knowledge-workspace.test.tsx` |
| Semantic retrieval beyond five records | Focused integration assertion exposed the API's exact status value while proving the fake semantic provider path executed | `1 passed, 31 deselected`; relevant seventh record was the sole narrative evidence in the provider prompt |
| Residual PII regression found by full suite | Full run: `191 passed, 1 failed`; the detector re-matched an already sanitized address label | Focused regression: `2 passed, 30 deselected`; final full suite green |

## Implemented remediation

- Expanded normalized multilingual free-text and structured PII redaction.
  Residual supported PII now stores only `[REDACTED: PII]`, records
  `pii_detected`, requires handoff, and skips model invocation.
- Expanded deterministic severe-health detection; severe results skip the
  model regardless of model output.
- Suggestions are discarded as a generation unless every one references a
  fresh, selected SQL SKU snapshot. Typed fact claims and prose claims are
  checked against price/currency, inventory, origin, weight, and shipping ETA.
- Evaluation requires exact line-scoped message pairing, treats explicit
  invalid facts as errors, and counts high-risk recall only with handoff.
- A single app-state embedding provider is injected into knowledge writes,
  updates, and copilot queries. Model/version metadata is stored and used to
  restrict retrieval. Deterministic embeddings are development/test-only.
- Aware, future validity timestamps and aware outcome timestamps are enforced.
  Expiry is exclusive at the exact boundary.
- Migration `0008` adds embedding metadata, tenant-scoped responsible-user FK
  and index, case enum checks, and citation type checks, with safe downgrade.
- Knowledge editing now supports type, source, owner UUID, validity, and
  content. Browser-local datetime values are converted to ISO for writes and
  API timestamps are converted back for editing.

## Final verification

Backend:

- `python -m pytest -q` -> `192 passed in 27.01s`
- `python -m ruff check .` -> `All checks passed!`
- `python -m mypy --strict src` -> `Success: no issues found in 54 source files`
- `alembic upgrade head` -> success
- `alembic downgrade base` -> success
- `alembic upgrade head` -> success; database left at head

Frontend (`CI=true`, bundled Node/pnpm):

- `pnpm test` -> `4 passed`, `28 passed`
- `pnpm lint` -> success
- `pnpm build` -> successful Next production build and TypeScript validation
- `apps/web/next-env.d.ts` remained unchanged

Repository:

- `git diff --check` -> success

## Self-review

- Tenant boundaries are enforced in service lookups and by the new composite
  responsible-user foreign key.
- Unsafe model generations are discarded atomically; no partial set of
  suggestions is persisted.
- Redacted content is used for persistence, prompts, and downstream safety
  checks; tests inspect both API responses and provider arguments.
- Embedding query/write model metadata is consistent, and production absence
  fails closed.
- Migration upgrade/downgrade behavior and database rejection paths are tested
  directly.
- Existing endpoint wire names and review-reset behavior remain compatible.

## Concerns and documented limitations

- The current API has no authenticated session/role-discovery endpoint for the
  web client. The UI therefore does not infer role authority from client data;
  server authorization remains authoritative as required.
- `copilot_suggestions` has no risk-level or status columns in the approved
  schema, so no suggestion risk/status CHECK could be added. Case risk/status
  and citation type values are constrained. This brief wording appears to
  refer to concepts that only exist on `copilot_cases`.
- Browser automation was unavailable in this environment. Frontend behavior
  was validated through focused Testing Library coverage, full Vitest, ESLint,
  TypeScript, and the production Next build.
