# Independent review remediation report 3

Date: 2026-07-20

## Scope and hashes

- Review result addressed: `CHANGES_REQUIRED`
- Starting review commit: `29442296129c44a7c80b2729d6bb77783f7e7707`
- Remediation implementation commit: `55fc11c929fe2c7515b255a1e6e6f49a7f76fcf6`
- Branch: `agent/implement-weeks-3-4-copilot`

## Focused RED/GREEN evidence

| Review slice | RED | GREEN |
| --- | --- | --- |
| Unified PII labels and values | 11 new unit failures for social/payment handles, QQ/扣扣, Alipay username, customer/recipient names, Chinese structured keys, and ambiguous labels | `test_redaction.py`: `31 passed` |
| API/PATCH residual PII | New API cases exposed labeled/residual variants; the manual edit path could persist `contact wxid_alice123` | Focused API/PATCH set: `15 passed, 36 deselected`; provider input and persisted history contain no raw PII |
| Complete typed fact claims | Missing and partial `fact_claims` were accepted by the provider output schema | Missing/partial claims now raise `ValidationError`; complete claims are mandatory |
| Structural fact boundary | Nine reviewer phrases, including `It is 39.90`, `seven remain`, `Grown in`, and `这是3kg装`, initially caused handoff or depended on prose parsing | Focused schema/rendering set: `13 passed, 38 deselected`; valid outputs persist only canonical server-rendered SQL facts |
| Production provider misinjection | A deterministic embedding provider injected in production returned HTTP 500 | Route preflight now returns the error-contract HTTP 503; regression passed |

The copilot compatibility suite completed with `54 passed` after updating one
legacy assertion to the canonical server-rendered suggestion.

## Security design

### PII boundary

- English and Chinese sensitive keys and labels are defined in one canonical
  family map covering QQ/扣扣, payment/Alipay, social handles, WeChat, and
  customer/recipient names.
- Reliable labeled values are replaced without treating connector or sentinel
  words such as `is`, `username`, `unknown`, or `unavailable` as the value.
- If a sensitive label remains after reliable parsing, or an independent
  residual scan still detects PII, the entire string becomes
  `[REDACTED: PII]`.
- Case creation and recursive manual suggestion edits use the same sanitizer.
  Consequently residual values such as `contact wxid_alice123` cannot reach
  model prompts, API history, or database persistence.

### Fact boundary

- `fact_claims` is non-null and requires price, currency, inventory, origin,
  and net weight. Optional SQL fields must still be represented explicitly as
  `null`.
- The model may rank/select a SKU, but every typed claim must exactly match the
  fresh tenant-scoped SQL SKU snapshot. A claimed shipping ETA is also checked.
- Model suggestion prose is never persisted or returned. Once the selected SKU
  and complete claims pass validation, the server renders the final text from
  that same SQL snapshot using a fixed template.
- This removes prose parsing as a trust boundary: alternate phrasing, duplicate
  spans, and concealed free-text claims cannot affect persisted facts.

### Provider configuration boundary

- Knowledge create/update routes reject a missing or environment-disallowed
  embedding provider before entering the service, producing an explicit 503
  instead of leaking an internal RuntimeError as a 500.

## Final verification

Backend:

- `python -m pytest -q` -> `238 passed in 34.57s`
- `python -m ruff check .` -> `All checks passed!`
- `python -m mypy src tests` with project strict mode -> `Success: no issues found in 86 source files`
- `alembic upgrade head` -> success
- `alembic downgrade base` -> success
- `alembic upgrade head` -> success; database left at head

Frontend (`CI=true`, bundled Node/pnpm):

- `pnpm test` -> `4 passed`, `29 passed`
- `pnpm lint` -> success
- `pnpm build` -> successful Next production build and TypeScript validation
- `apps/web/next-env.d.ts` remained unchanged

Repository:

- `git diff --check` -> success

## Self-review

- Regression tests assert provider non-invocation for fail-closed PII cases and
  inspect both API history and persisted edit results.
- Fact regressions cover all supplied English and Chinese reviewer phrases,
  correct matching claims, and contradictory structured price, inventory,
  origin, and weight.
- Canonical rendering uses only the validated SQL object, so no model-authored
  fact prose crosses the persistence/output boundary.
- The production-provider test exercises the real API error envelope.

## Limitations

- Browser automation remains unavailable in this environment. Frontend safety
  is covered by Testing Library/Vitest, ESLint, TypeScript, and the production
  Next build.
