# Full Branch Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the final safety, auditability, case-history, evidence, conflict, discovery, and UI authorization gaps identified by the complete branch review.

**Architecture:** Keep deterministic safety decisions in the copilot service, append-only business events in the existing outcome table, and immutable operational traces in `AuditService`. Migration `0009` extends cases and citation snapshots without rewriting historical facts. Tenant-scoped repositories provide explicit SKU discovery/conflict and approved narrative search; API schemas expose server-derived timelines, adoption state, latency, and citation timestamps. The frontend consumes those server fields and session permissions rather than browser timing or optimistic role assumptions.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy async, Alembic/PostgreSQL RLS, pytest; React 19, Next.js 16, TypeScript, Vitest/Testing Library.

## Global Constraints

- Every production behavior starts with a focused failing test and observed RED.
- Model output may increase risk but may never downgrade deterministic handoff rules.
- All writes emit immutable audit events with recursively redacted payloads.
- Outcome state remains append-only and is derived for API/UI reads.
- Tenant scoping and existing permission checks remain authoritative.
- `apps/web/next-env.d.ts` must remain unchanged.
- Formal plan and report live under `docs/superpowers`; no `.superpowers` artifacts are committed.

---

### Task 1: Deterministic high-risk and direct-handoff safety

**Files:**
- Modify: `apps/api/src/fruit_agent/copilot/safety.py`
- Modify: `apps/api/src/fruit_agent/copilot/service.py`
- Test: `apps/api/tests/unit/test_safety.py`
- Test: `apps/api/tests/integration/test_copilot_api.py`

**Interfaces:**
- Consumes: deterministic `SafetyClassification` and typed model stage/intent/risk.
- Produces: a final merged classification where deterministic and model direct-handoff intents are monotonic.

- [ ] **Step 1: Write focused failing tests**

```python
assert classify_customer_message("这件事已经上热搜").requires_handoff is True
assert classify_customer_message("This complaint went viral").risk in {
    CopilotRisk.high,
    CopilotRisk.critical,
}
```

Add API cases where the provider returns `health_safety` with `low`/`medium`;
assert `handoff_required`, no suggestions, and provider prose absent. Add viral
message cases asserting provider non-invocation.

- [ ] **Step 2: Verify RED**

Run the named safety and API tests. Expected: viral phrases remain low-risk and
model `health_safety` suggestions persist.

- [ ] **Step 3: Implement monotonic intent/risk merge**

Introduce a controlled direct-handoff intent set containing
`health_safety`, `refund`, `complaint`, and `damage`. Re-evaluate handoff after
model enum selection; never replace a deterministic direct-handoff intent with
a lower-risk model path. Add completed-action viral patterns in both languages.

- [ ] **Step 4: Verify GREEN**

Re-run the focused tests and require provider non-invocation for deterministic
viral cases and suggestion disposal for model-only handoff intents.

### Task 2: Audit every write and expose append-only case history

**Files:**
- Modify: `apps/api/src/fruit_agent/knowledge/router.py`
- Modify: `apps/api/src/fruit_agent/copilot/router.py`
- Modify: `apps/api/src/fruit_agent/copilot/models.py`
- Modify: `apps/api/src/fruit_agent/copilot/repository.py`
- Modify: `apps/api/src/fruit_agent/copilot/schemas.py`
- Test: `apps/api/tests/integration/test_audit.py`
- Test: `apps/api/tests/integration/test_copilot_outcomes_api.py`
- Test: `apps/api/tests/integration/test_copilot_api.py`

**Interfaces:**
- Consumes: `AuditService.record`, `CopilotOutcomeEvent`.
- Produces: audit rows for knowledge create/edit/review, case create, suggestion
  edit, and every non-duplicate outcome; `CopilotCaseRead.outcomes`; derived
  `CopilotSuggestionRead.adoption_status`.

- [ ] **Step 1: Write audit and timeline RED tests**

Assert one audit row per successful write, no duplicate audit on idempotent
outcome replay, recursively redacted nested PII, complete ordered outcome
timeline on case detail, and adoption status derived from the latest append-only
adopt/reject event.

- [ ] **Step 2: Verify RED**

Expected: knowledge/case/edit writes have no audit rows and case detail omits
outcomes/adoption status.

- [ ] **Step 3: Add immutable audit hooks and eager loading**

Pass the request ID into write routers and record before/after wire-safe
snapshots inside the tenant transaction. Add read-only ORM relationships for
case outcomes and suggestion outcomes; eager-load both in list/detail and map
them through Pydantic computed response fields.

- [ ] **Step 4: Verify GREEN**

Re-run audit/outcome API tests and inspect `audit_events` plus
`copilot_outcome_events` directly.

### Task 3: Migration 0009, latency, and citation provenance

**Files:**
- Create: `apps/api/migrations/versions/0009_case_timing_and_citation_provenance.py`
- Modify: `apps/api/src/fruit_agent/copilot/models.py`
- Modify: `apps/api/src/fruit_agent/copilot/schemas.py`
- Modify: `apps/api/src/fruit_agent/copilot/service.py`
- Test: `apps/api/tests/integration/test_final_migration_invariants.py`
- Test: `apps/api/tests/integration/test_copilot_api.py`

**Interfaces:**
- Produces: `CopilotCase.response_time_ms: int`; citation
  `source_updated_at` and `retrieved_at` timestamps.

- [ ] **Step 1: Write migration/API RED tests**

```python
assert body["response_time_ms"] >= 0
assert citation["source_updated_at"] is not None
assert citation["retrieved_at"] is not None
```

Assert create, history, and detail return the same server timing; SKU and
knowledge citations persist source update and retrieval instants.

- [ ] **Step 2: Verify RED**

Expected: response keys and migration columns are absent.

- [ ] **Step 3: Implement 0009 and service timing**

Add non-negative integer case timing with a safe historical default. Add
timezone-aware citation timestamps with historical backfill from
`copilot_citation_snapshots.created_at`. Measure the complete server create
operation with `perf_counter`, set the case field before final flush, and stamp
citations from each source's `updated_at` plus a single retrieval instant.

- [ ] **Step 4: Verify GREEN and round trip**

Run focused tests, then Alembic `head -> 0008 -> head`, confirming historical
rows remain readable.

### Task 4: SKU conflict discovery, body SKU extraction, and public narrative search

**Files:**
- Modify: `apps/api/src/fruit_agent/knowledge/repository.py`
- Modify: `apps/api/src/fruit_agent/knowledge/service.py`
- Modify: `apps/api/src/fruit_agent/knowledge/schemas.py`
- Modify: `apps/api/src/fruit_agent/knowledge/router.py`
- Modify: `apps/api/src/fruit_agent/copilot/service.py`
- Modify: `apps/api/src/fruit_agent/copilot/schemas.py`
- Test: `apps/api/tests/integration/test_knowledge_queries.py`
- Test: `apps/api/tests/integration/test_copilot_api.py`
- Test: `apps/api/tests/integration/test_knowledge_management_api.py`

**Interfaces:**
- Produces: `handoff_reason` plus complete `conflict_source_ids`; tenant-scoped
  SKU-code discovery; `GET /api/v1/knowledge/items/search`.

- [ ] **Step 1: Write RED tests**

Cover two or more conflicting SKU sources in both exact-fact and copilot
responses; extract explicit SKU codes from message text, merge/deduplicate with
selected codes, cap at three, and exclude foreign-tenant codes. Search tests
cover maintenance-role permission, tenant isolation, approved/unexpired
narrative type whitelist, limit, and route precedence.

- [ ] **Step 2: Verify RED**

Expected: case handoff omits IDs/reason, body-only SKU is ignored, and search is
404 or captured by the item route.

- [ ] **Step 3: Implement tenant-scoped discovery and search**

Query candidate tenant SKU codes and match them as bounded literals in the
message. Merge explicit selections first, then discovered codes, preserving
order and limiting to three. Carry all conflict source IDs through case schema.
Place `/items/search` before `/{knowledge_id}` routes and call the existing
approved/fresh semantic repository with only FAQ/talking-point/origin-story.

- [ ] **Step 4: Verify GREEN**

Re-run knowledge/copilot focused suites and inspect provider prompts for the
merged, tenant-safe SKU evidence.

### Task 5: Session permissions, conflict UI, outcome timeline, and rejection

**Files:**
- Modify: `apps/api/src/fruit_agent/identity/router.py`
- Modify: `apps/api/src/fruit_agent/identity/schemas.py`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/components/copilot/copilot-workspace.tsx`
- Modify: `apps/web/components/copilot/case-panel.tsx`
- Modify: `apps/web/components/copilot/suggestion-card.tsx`
- Modify: `apps/web/components/knowledge/knowledge-workspace.tsx`
- Modify: `apps/web/components/knowledge/knowledge-table.tsx`
- Test: `apps/web/tests/copilot-workspace.test.tsx`
- Test: `apps/web/tests/knowledge-workspace.test.tsx`

**Interfaces:**
- Produces: `GET /api/v1/session` with role/permissions; reject button sending
  idempotent `suggestion_rejected`; server timeline rendering; permission-aware
  knowledge actions; SKU conflict display.

- [ ] **Step 1: Write frontend/API RED tests**

Assert switching historical cases displays that case's payment/refund/
complaint/adopt/close timeline and server `response_time_ms`. Assert rejection
uses a stable idempotency key across retry. Assert support users cannot see
knowledge create/edit/review controls while operator/implementer controls match
server permissions. Assert conflict source IDs render.

- [ ] **Step 2: Verify RED**

Expected: browser timing is displayed, events reset on switch, reject control is
absent, and all knowledge buttons render regardless of role.

- [ ] **Step 3: Implement the minimal client changes**

Load session once, consume timeline embedded in case detail, display derived
adoption state, use `response_time_ms`, add reject event action with a retained
idempotency key, and pass permission booleans to knowledge form/table.

- [ ] **Step 4: Verify GREEN**

Run the two frontend test files, then the full frontend suite, lint, and build.

### Task 6: Full verification and formal report

**Files:**
- Create: `docs/superpowers/reports/2026-07-20-full-branch-readiness-report.md`

- [ ] **Step 1: Run backend verification**

Run full pytest, Ruff, strict mypy, and Alembic `head -> base -> head`.

- [ ] **Step 2: Run frontend verification**

Run Vitest, ESLint, and production Next build with `CI=true`; verify
`next-env.d.ts` is unchanged.

- [ ] **Step 3: Audit repository and write report**

Run `git diff --check`, inspect migration downgrade/upgrade, search all write
routes for audit coverage, and record exact RED/GREEN/full-suite evidence in
the report.

- [ ] **Step 4: Commit**

Commit the implementation and formal report under `docs/superpowers`.
