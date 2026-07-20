# Weeks 3–4 Trusted Knowledge and Copilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for every behavior change. Each task must be committed and independently verified.

**Goal:** Deliver a tenant-safe, human-in-the-loop customer-service copilot backed only by fresh, approved merchant knowledge.

**Architecture:** Add an isolated `copilot` domain module that orchestrates deterministic safety rules, the existing knowledge repository, and the provider-neutral model gateway. Persist redacted cases, suggestion/citation snapshots, and append-only outcome events under PostgreSQL RLS; expose them through FastAPI and the existing Next.js workspace.

**Tech Stack:** Python 3.12, FastAPI 0.139, SQLAlchemy 2, PostgreSQL 18/pgvector, Pydantic 2, Next.js 16.2, React 19, Vitest.

## Global Constraints

- Never persist or send an unredacted customer message to a model.
- Never read or send Feige messages or execute refunds, compensation, price, inventory, or publishing actions.
- Exact SKU facts use SQL; semantic retrieval is limited to approved, unexpired `faq`, `talking_point`, and `origin_story` records.
- Expired facts, conflicting sources, high/critical risk, invalid citations, missing evidence, or unavailable models fail closed to `handoff_required`.
- Model output may raise risk but never lower deterministic risk.
- All tenant-owned tables use explicit `tenant_id` filters plus PostgreSQL `FORCE ROW LEVEL SECURITY`.
- Roles: owner/operator/support use copilot and record outcomes; owner/operator/implementer maintain knowledge; only owner/implementer approve knowledge.
- Synchronous response target is P95 under 8 seconds; failures return degraded/handoff within 15 seconds.
- Existing `/api/v1/model-gateway/suggestions` behavior remains compatible.

---

### Task 1: Trusted knowledge management and retrieval

**Deliverable:** Migration `0005` extends SKU facts and narrative knowledge, adds provider-neutral embeddings, and exposes real list/create/update/review APIs.

**Interfaces:**

- `EmbeddingProvider.embed(text: str) -> list[float]`; deterministic 1536-dimension implementation for tests/development.
- `GET /api/v1/knowledge/items`
- `POST /api/v1/knowledge/items`
- `PATCH /api/v1/knowledge/items/{knowledge_id}`
- `POST /api/v1/knowledge/items/{knowledge_id}/review`
- New writes require `source_name`, `responsible_user_id`, `valid_until`; content edits reset review status to `draft`.
- Extend `ProductSKU` with nullable `variety`, `origin`, `orchard`, `taste`, `ripeness`, `specification`, `net_weight_grams`, `sales_regions`, and `shipping_eta`.

**Tests first:**

- Knowledge create/list/update/review permissions and tenant isolation.
- Content edit resets approval; rejected/draft/expired knowledge cannot be retrieved.
- Deterministic embeddings are stable and exactly 1536 dimensions.
- Exact SKU conflict/expiry behavior remains fail closed.
- Run API unit/integration/security suites, Ruff, and mypy.

### Task 2: Copilot cases, risk rules, suggestions, and citations

**Deliverable:** Migration `0006` and a new `copilot` module implement case creation, classification, retrieval, structured suggestions, citation validation, history, and detail APIs.

**Interfaces:**

- `POST /api/v1/copilot/cases` with `{message: str, selected_sku_codes: string[0..3]}`.
- `GET /api/v1/copilot/cases?limit=&offset=`
- `GET /api/v1/copilot/cases/{case_id}`
- `PATCH /api/v1/copilot/cases/{case_id}/suggestions/{suggestion_id}` with `{edited_text}`.
- Enums exactly match the approved plan: stage, intent, risk, case status.
- Return at most three suggestions, each with a tenant-validated SKU and immutable citation snapshots.

**Tests first:**

- Every mandatory high-risk category hands off without suggestions.
- Rule risk can only be upgraded by a model result.
- Redaction occurs before persistence and provider invocation.
- Fresh evidence creates suggestions; missing/expired/conflicting evidence hands off.
- Unknown/cross-tenant citations and unapproved knowledge are rejected.
- Cross-tenant case/history/detail access is hidden.
- Provider failure returns `degraded` or `handoff_required`, never an unsafe draft.

### Task 3: Outcome events, audit, and evaluation

**Deliverable:** Append-only outcome recording, idempotency, immutable auditing, and an offline agent-evaluation command with synthetic fixtures.

**Interfaces:**

- `POST /api/v1/copilot/cases/{case_id}/events` requires `Idempotency-Key`.
- Event types: `suggestion_adopted`, `suggestion_rejected`, `payment`, `refund`, `complaint`, `case_closed`.
- Duplicate tenant/case/idempotency keys return the original event without duplication.
- Evaluation input is UTF-8 JSONL with redacted message, expected stage/intent/risk/handoff, allowed citations, and optional expected SKU.
- Report stage accuracy, intent accuracy, high-risk recall, citation validity, and factual-error rate.

**Tests first:**

- Event idempotency, case/suggestion ownership, closed status transition, audit redaction, and cross-tenant denial.
- Evaluation metric calculations including zero-denominator behavior.
- Migration upgrade/downgrade and full back-end verification.

### Task 4: Copilot workspace and dynamic knowledge UI

**Deliverable:** Production-oriented `/copilot` workflow and a live `/knowledge` page using the new APIs.

**Interfaces and behavior:**

- Add typed API helpers for cases, suggestions, events, and knowledge.
- Copilot form accepts a 1–4000 character pasted message and up to three SKU codes.
- Render classification, risk, handoff/degraded state, editable suggestion cards, confidence, risk tips, expandable citations, history, and outcomes.
- “采纳并复制” copies first and then posts an idempotent adoption event; failures are visible and retryable.
- Knowledge UI lists source, owner, status, freshness, and supports create/edit/review according to role/API enforcement.
- Preserve the existing green/white workspace, table-led density, responsive navigation, focus visibility, semantic labels, and reduced-motion behavior.

**Tests first:**

- Successful suggestions, handoff state, edit/adopt-copy retry, citations, result events, loading/error states, and live knowledge rendering.
- Run Vitest, ESLint, TypeScript/Next production build, then complete API and repository verification.

