# Independent review remediation report 2

Date: 2026-07-20

## Scope and hashes

- Review result addressed: `CHANGES_REQUIRED`
- Starting review commit: `300233f5402fc376047ee3eb3cd1044f4ac3529b`
- Remediation implementation commit: `d17d01027fd2efe145b7fd3ec51d6a4dbc128b1a`
- Branch: `agent/implement-weeks-3-4-copilot`

## Focused RED/GREEN evidence

| Review slice | RED | GREEN |
| --- | --- | --- |
| Expanded PII replacement and recursive residual handling | `test_redaction.py`: 7 failures for `is/是/为`, Chinese keys, and nested residual PII | `21 passed`; copilot API PII set `6 passed`; nested outcome/audit snapshot assertions passed |
| Exhaustive fact parsing and prose/structured alignment | 8 new bypasses initially persisted suggestions, including currency-first/suffix price, `come from`, `in stock`, pack weight, true-then-false, and ambiguous prose | 17 contradictory variants passed; matching prose plus typed claims passed |
| Complete structured SKU prompt | Semantic prompt regression failed because six SKU fields were absent | Semantic retrieval/prompt regression passed with variety, orchard, ripeness, specification, net weight, and sales regions |
| Lazy/production-safe embedding dependency | Production deterministic write test reached persistence; embed/search integration returned HTTP 500 twice | Embedding unit set `4 passed`; embed/search failures `2 passed`; provider-free list/review/exact route passed |
| Severe health variants | 4 failures for collapsed, unresponsive, could-not-breathe, and Chinese post-consumption unresponsiveness | Safety focused suite passed; three API variants proved provider non-invocation |
| Evaluation factual denominator | Union-denominator regression returned `1.0` instead of `2/3` | Regression passed using the de-duplicated union of SKU and explicit fact labels |
| Non-UTC timestamp round-trip | Added backend `+08:00` instant and frontend non-UTC edit round-trip coverage | Backend focused suite and frontend knowledge suite (`9 passed`) passed |

The combined changed backend test set completed with `158 passed` before the
final full run.

## Remediation details

- Free-text redaction now handles `QQ/Alipay/WeChat/customer name` labels with
  `is`, `是`, and `为`. Unicode-sensitive structured keys are normalized
  without dropping Chinese characters.
- Recursive redaction performs replacement first and an independent residual
  scan second. Any residual supported PII becomes `[REDACTED: PII]`; this path
  is shared by model prompts, outcome metadata, and audit snapshots.
- Prose fact validation enumerates every recognized match. It supports
  currency-first and Chinese-suffix prices, English/Chinese origins,
  number-before-stock inventory, and pack weights. Every recognized prose
  fact must agree with both the exact SQL SKU snapshot and typed
  `fact_claims`; ambiguous fact language fails closed.
- The model prompt now includes all relevant structured SKU fields while
  server-side validation remains authoritative.
- Embedding resolution is lazy for read/review/exact operations. Writes still
  require an allowed provider, and production rejects deterministic hashing.
- Provider embedding and vector-search failures are isolated and converted
  into a persisted `handoff_required` case with
  `embedding_provider_error`; the model is not called.
- Severe deterministic patterns include collapsed, unresponsive,
  could-not/couldn't-breathe, and Chinese post-consumption unresponsiveness.
- Factual error evaluation uses the row union of `expected_sku_code` and an
  explicit `factual_claims_valid` label, counting each row once.
- Backend and frontend tests prove `+08:00` values preserve the same instant
  through API/local datetime conversion.

## Final verification

Backend:

- `python -m pytest -q` -> `223 passed in 32.84s`
- `python -m ruff check .` -> `All checks passed!`
- `python -m mypy --strict src` -> `Success: no issues found in 54 source files`
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

- API tests inspect both persisted/history content and actual provider prompt
  arguments for the added PII bypasses.
- Nested metadata proves the same fail-closed sanitizer reaches outcome and
  audit persistence.
- Fact validation rejects every match if any later claim contradicts the SKU;
  a correct earlier match cannot mask a false later match.
- Embedding search runs inside a database savepoint for a real async session,
  allowing the already-created safe handoff case to flush after search errors.
- Read-only knowledge paths no longer constructively depend on an embedding
  provider; content writes and re-embedding remain strict.
- No existing safety condition was downgraded or removed.

## Limitations

- Browser automation remains unavailable in this environment. The frontend
  change is covered by Testing Library, full Vitest, ESLint, TypeScript, and a
  production Next build.
