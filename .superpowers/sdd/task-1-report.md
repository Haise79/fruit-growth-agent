# Task 1 report: trusted knowledge management and retrieval

## Changed files

- `apps/api/migrations/versions/0005_knowledge_management.py`
- `apps/api/src/fruit_agent/identity/service.py`
- `apps/api/src/fruit_agent/knowledge/embeddings.py`
- `apps/api/src/fruit_agent/knowledge/models.py`
- `apps/api/src/fruit_agent/knowledge/repository.py`
- `apps/api/src/fruit_agent/knowledge/router.py`
- `apps/api/src/fruit_agent/knowledge/schemas.py`
- `apps/api/src/fruit_agent/knowledge/service.py`
- `apps/api/tests/integration/test_knowledge_management_api.py`
- `apps/api/tests/integration/test_knowledge_queries.py`
- `apps/api/tests/unit/test_embeddings.py`
- `apps/api/tests/unit/test_knowledge_freshness.py`

`fruit_agent.app` already registered the knowledge router, so no app registration change was needed.

## RED phase

1. `D:\\Agent\\电商系统\\fruit-growth-agent\\.worktrees\\weeks-1-2-foundation\\apps\\api\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_embeddings.py tests/integration/test_knowledge_management_api.py -q`
   - Failed during collection as expected: `ModuleNotFoundError: fruit_agent.knowledge.embeddings`.
2. `D:\\Agent\\电商系统\\fruit-growth-agent\\.worktrees\\weeks-1-2-foundation\\apps\\api\\.venv\\Scripts\\python.exe -m pytest tests/integration/test_knowledge_management_api.py -q`
   - Failed as expected: both new item-management API tests received `404` because the routes did not exist.

## GREEN phase

`D:\\Agent\\电商系统\\fruit-growth-agent\\.worktrees\\weeks-1-2-foundation\\apps\\api\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_embeddings.py tests/unit/test_knowledge_freshness.py tests/integration/test_knowledge_management_api.py tests/integration/test_knowledge_queries.py -q`

Result: `7 passed`.

## Full verification

- `python -m pytest tests/unit tests/integration tests/security -q` — `49 passed`.
- `python -m ruff check src tests migrations` — `All checks passed!`.
- `python -m mypy src tests` — `Success: no issues found in 68 source files`.
- `git diff --check` — no whitespace errors.

## Self-review

- New knowledge writes require source name, responsible user ID, and validity timestamp; they are drafted and embedded through a provider-neutral interface.
- Content edits recompute embeddings and reset approval to `draft`; only owner and implementer roles have review permission.
- Repository access keeps explicit tenant predicates and each API operation runs inside an explicit tenant transaction. Cross-tenant updates return `404`.
- Semantic search remains fail-closed for draft, rejected, expired, and non-narrative knowledge. Existing exact SKU expiry and conflict behavior remains covered.
- Migration `0005` adds the requested nullable SKU narrative fields and preserves existing direct knowledge inserts with a legacy source-name default while API writes stay strict.

## Commit and concerns

Initial implementation commit: `bd547fd1af34cc7dcb28f4d769078284b9c7469c`.

No implementation concerns.

## Review-fix evidence

### RED phase

`D:\\Agent\\电商系统\\fruit-growth-agent\\.worktrees\\weeks-1-2-foundation\\apps\\api\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_knowledge_freshness.py tests/integration/test_knowledge_management_api.py -q`

Result: `5 failed, 5 passed`, with the expected failures:

- a SKU differing only in `variety` was returned as `ok`;
- explicit `null` updates returned `200` or an uncaught database-error `500` instead of `422`;
- a tenant-B responsible user was accepted for a tenant-A knowledge record.

### GREEN and full verification

- Focused: `python -m pytest tests/unit/test_knowledge_freshness.py tests/integration/test_knowledge_management_api.py -q` — `10 passed`.
- Full API verification: `python -m pytest tests/unit tests/integration tests/security -q` — `55 passed`.
- `python -m ruff check src tests migrations` — `All checks passed!`.
- `python -m mypy src tests` — `Success: no issues found in 68 source files`.
- `git diff --check` — no whitespace errors.

### Review-fix commit

`9141623693064ca3e282a53a35c56cda9827693a` — hardens SKU conflict comparison, nullable update validation, responsible-member validation, and cross-tenant API coverage.

## Approval-reset review-fix evidence

### RED phase

`D:\\Agent\\电商系统\\fruit-growth-agent\\.worktrees\\weeks-1-2-foundation\\apps\\api\\.venv\\Scripts\\python.exe -m pytest tests/integration/test_knowledge_management_api.py -q`

Result: `5 failed, 7 passed`. The four retrieval/provenance/freshness edits left
approved records approved, and extending validity left the record semantically eligible.

### GREEN and full verification

- Focused: `python -m pytest tests/integration/test_knowledge_management_api.py -q` — `12 passed`.
- Full API verification: `python -m pytest tests/unit tests/integration tests/security -q` — `60 passed`.
- `python -m ruff check src tests migrations` — `All checks passed!`.
- `python -m mypy src tests` — `Success: no issues found in 68 source files`.
- `git diff --check` — no whitespace errors.

### Approval-reset review-fix commit

`7ee7ef7e9f5d323c241f2a821e811600a14ca997` — resets approved knowledge to
draft only when a persisted content, retrieval, provenance, or freshness value
actually changes; unchanged-value patches preserve approval.
