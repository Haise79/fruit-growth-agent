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

Commit hash: recorded in the task handoff after this report is committed.

No implementation concerns.
