# Task 2 report: copilot cases, risk rules, suggestions, and citations

## Changed files

- `apps/api/migrations/versions/0006_copilot_cases.py`
- `apps/api/src/fruit_agent/app.py`
- `apps/api/src/fruit_agent/common/redaction.py`
- `apps/api/src/fruit_agent/copilot/__init__.py`
- `apps/api/src/fruit_agent/copilot/models.py`
- `apps/api/src/fruit_agent/copilot/repository.py`
- `apps/api/src/fruit_agent/copilot/router.py`
- `apps/api/src/fruit_agent/copilot/safety.py`
- `apps/api/src/fruit_agent/copilot/schemas.py`
- `apps/api/src/fruit_agent/copilot/service.py`
- `apps/api/src/fruit_agent/identity/service.py`
- `apps/api/src/fruit_agent/model_gateway/ports.py`
- `apps/api/src/fruit_agent/model_gateway/schemas.py`
- `apps/api/src/fruit_agent/model_gateway/service.py`
- `apps/api/tests/integration/test_copilot_api.py`
- `apps/api/tests/unit/test_copilot_model_gateway.py`
- `apps/api/tests/unit/test_copilot_safety.py`

No outcome-event or frontend files were changed.

## Baseline

Command:

`D:\Agent\电商系统\fruit-growth-agent\.worktrees\weeks-1-2-foundation\apps\api\.venv\Scripts\python.exe -m pytest -q`

Result before Task 2 changes: `60 passed in 7.52s`.

## RED phase

1. Deterministic safety rules:
   - Command: `python -m pytest -q tests/unit/test_copilot_safety.py`
   - Initial collection failed because `fruit_agent.copilot` did not exist.
   - After adding only the wished-for interface skeleton, the suite failed as
     expected: `9 failed, 1 passed`; every mandatory risk family and risk
     upgrade behavior exposed the missing implementation.
2. Typed copilot gateway and embedded-content redaction:
   - Command: `python -m pytest -q tests/unit/test_copilot_model_gateway.py`
   - Initial collection failed because the typed copilot gateway schemas did
     not exist.
   - After adding the typed contract, the test failed because the embedded
     mobile number still reached the provider.
3. Copilot API, persistence, evidence, citations, tenant isolation, and edit:
   - Command: `python -m pytest -q tests/integration/test_copilot_api.py`
   - Result: `12 failed`; every request received the expected `404` because the
     copilot router and migration did not exist.
4. Bulk spoilage and public-opinion rules:
   - Command: `python -m pytest -q tests/unit/test_copilot_safety.py`
   - Result: `2 failed, 10 passed`; independent bulk spoilage and independent
     public-opinion threats exposed the missing fail-closed branches.
5. Bilingual mandatory risk rules:
   - Command: `python -m pytest -q tests/unit/test_copilot_safety.py -k english`
   - Result: `6 failed, 12 deselected`; English health, food-safety, bulk,
     regulator, refund-dispute, and injury messages were not yet classified.
6. Independent security-review regressions:
   - Command:
     `python -m pytest -q tests/unit/test_copilot_model_gateway.py::test_copilot_retry_and_failover_share_one_total_deadline tests/integration/test_copilot_api.py::test_unexpected_provider_error_persists_handoff_case tests/integration/test_copilot_api.py::test_unrelated_narrative_is_not_accepted_as_customer_evidence`
   - Result: `3 failed`; aggregate retry latency exceeded its deadline,
     unexpected SDK errors returned `500`, and unrelated narrative evidence
     produced `suggestions_ready`.

## GREEN phase

1. Mandatory safety rules and risk monotonicity:
   - `python -m pytest -q tests/unit/test_copilot_safety.py`
   - Result: `18 passed`.
2. Copilot API integration:
   - `python -m pytest -q tests/integration/test_copilot_api.py`
   - Initial core result: `12 passed`.
3. Security-review fixes:
   - The aggregate provider deadline, unexpected-provider-error handoff, and
     narrative relevance regressions all passed: `3 passed`.
4. Final focused verification:
   - Command:
     `python -m pytest -q tests/unit/test_copilot_safety.py tests/unit/test_copilot_model_gateway.py tests/integration/test_copilot_api.py tests/unit/test_model_failover.py tests/integration/test_foundation_flow.py tests/security/test_prompt_redaction.py`
   - Result: `37 passed in 5.60s`.

## Full verification

- `python -m pytest -q` — `94 passed in 12.34s`.
- `python -m ruff check .` — `All checks passed!`.
- `python -m mypy src tests` — `Success: no issues found in 78 source files`.
- `git diff --check` — no whitespace errors.
- Integration fixtures repeatedly upgraded through migration `0006` and
  downgraded to base successfully.

## Self-review

- Customer messages and suggestion edits are redacted before persistence;
  typed copilot prompts are redacted again at the gateway boundary.
- Mandatory deterministic safety families return persisted
  `handoff_required` cases without invoking a provider. Model risk is merged
  monotonically, and high/critical model drafts are discarded.
- Exact selected-SKU evidence is tenant-filtered and fails closed for missing,
  expired, or conflicting facts. Narrative evidence is limited to approved,
  unexpired allowed types and must also pass a lexical relevance gate.
- Model citations must belong to the fresh retrieved context, and recommended
  SKUs must belong to fresh selected context. Validation failure discards all
  drafts.
- Citation rows store immutable factual snapshots. Migration `0006` applies
  `FORCE ROW LEVEL SECURITY` to every new tenant-owned table and a database
  trigger rejects citation snapshot updates/deletes.
- Case history, detail, and edit repositories use explicit tenant predicates;
  cross-tenant resources are hidden with empty history or `404`.
- The existing `/api/v1/model-gateway/suggestions` request/response contract is
  unchanged. Copilot adds a separate typed output path while retaining quality
  gates, primary retries, fallback, redaction, and tenant citation validation.
- Copilot provider work has a shared 14-second deadline. Unexpected provider
  exceptions are treated as unavailable and produce a persisted safe handoff.
- Owner, operator, and support roles receive `copilot:use`; implementer does
  not. No refund, compensation, price, inventory, publishing, or Feige action
  interfaces were added.

## Independent security review

The internal reviewer reported no Critical findings and three Important
findings:

1. unexpected provider errors could return `500` and roll back the case;
2. retry plus failover could exceed the 15-second failure ceiling;
3. unrelated approved narrative knowledge could defeat missing-evidence
   fail-closed behavior.

All three findings were reproduced with failing tests, fixed, and included in
the final focused and full verification above.

## Commit and concerns

Implementation commit:
`1a8bed5dd3f99fc97dd1096d9fbdf896eaf71bdf`.

No unresolved implementation concerns. The relevance gate is intentionally
conservative: uncertain narrative matches hand off rather than generating an
unsupported draft.

## Independent review round 2 fixes

### Additional changed files

- `apps/api/src/fruit_agent/knowledge/schemas.py`
- `apps/api/tests/unit/test_copilot_evidence.py`
- `apps/api/tests/unit/test_redaction.py`

The existing migration, copilot safety/service/models, copilot integration
tests, and Task 2 report were also updated.

### RED evidence

1. Expanded deterministic handoff vocabulary:
   - Exact reviewer examples: `我有哮喘，可以吃吗？`,
     `吃完后一直腹泻呕吐`, and `我要去工商局投诉`.
   - Additional disease, adverse-symptom, consumer-association, and hotline
     variants were included.
   - Focused result: `8 failed, 1 passed, 18 deselected`.
2. Conservative narrative relevance:
   - A storage question and an apple-named employee scheduling document were
     incorrectly considered relevant, while a storage document using
     `冰箱` instead of the exact `冷藏` phrase was missed.
   - Focused result: `3 failed`.
3. Expanded free-text PII:
   - Synthetic unlabeled Shanghai address, landline, 19-digit card/account
     number, and passport ID remained in both the persisted case and provider
     prompt.
   - Focused result: `2 failed`.
4. SKU TOCTOU/requery:
   - After correcting the test fixture to include the database-generated SKU
     ID, the regression failed because evidence contained an ORM `ProductSKU`
     from a second query instead of the already validated `ProductSKURead`
     snapshot.
   - Focused result: `1 failed`.
5. Immutable citation FK semantics:
   - PostgreSQL reported `confdeltype = 'c'` (`CASCADE`) for the case-to-
     suggestion and both citation parent foreign keys.
   - Focused result: `1 failed`.

### GREEN evidence

- Expanded safety rules: `27 passed`.
- Topic-anchor evidence relevance, including realistic apple/scheduling
  regression: `3 passed`.
- Extended PII unit plus persisted-case/provider boundaries: `2 passed`.
- Validated SKU snapshot reuse plus fresh exact-evidence API: `2 passed`.
- Restrictive/no-action parent FK catalog check: `1 passed`.
- Consolidated affected suites:
  `python -m pytest -q tests/unit/test_copilot_safety.py
  tests/unit/test_copilot_evidence.py tests/unit/test_redaction.py
  tests/security/test_prompt_redaction.py
  tests/unit/test_copilot_model_gateway.py
  tests/integration/test_copilot_api.py` — `51 passed in 5.56s`.

### Round 2 full verification

- `python -m pytest -q` — `108 passed in 12.96s`.
- `python -m ruff check .` — `All checks passed!`.
- `python -m mypy src tests` —
  `Success: no issues found in 79 source files`.
- `python -m alembic upgrade head` — upgraded through `0006`.
- `python -m alembic downgrade base` — downgraded cleanly through `0001`.
- `git diff --check` — no whitespace errors.

### Round 2 self-review

- Mandatory deterministic handoff now conservatively covers common Chinese
  disease, adverse reaction, regulator, consumer-association, and hotline
  variants; all still skip provider invocation.
- Narrative eligibility requires shared intent/topic anchors. A product-name
  overlap alone cannot make unrelated narrative evidence eligible.
- Free-text redaction covers unlabeled Chinese delivery addresses, landlines,
  16–19 digit account/card numbers, and passport identifiers while retaining
  mobile, email, and national-ID behavior.
- Exact SKU evidence and citation content now use the same validated
  `ExactFactResult.sku` snapshot; no post-validation `rows[0]` requery remains.
- Immutable citation parent relationships use PostgreSQL `NO ACTION`.
  Citation updates/deletes remain rejected by the immutable trigger, while
  parent deletion is blocked instead of cascading into that trigger.

No unresolved round 2 concerns. Topic matching and PII detection remain
intentionally conservative and hand off/redact when uncertain.
