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
