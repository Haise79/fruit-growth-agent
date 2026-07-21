# Copilot Trusted Output Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent all model free text from being persisted or returned while producing intent-relevant suggestions from verified SQL and approved knowledge.

**Architecture:** Keep validation and assembly in `CopilotService`. Require a complete provider claim object, compare it to fresh SQL, de-duplicate verified SKU selections, and render deterministic intent templates plus an optional approved knowledge excerpt. Generate risk tips from a fixed server policy.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy async, pytest, PostgreSQL, React/Next.js regression suite.

## Global Constraints

- Strict RED → GREEN for every behavior change.
- Model `suggestion_text` and `risk_tip` must never be persisted or returned.
- `shipping_eta` must be present in provider output and may be null.
- Only fresh SQL and explicitly referenced approved knowledge may be rendered.
- Preserve tenant boundaries and existing fail-closed handoff behavior.

---

### Task 1: Close model free-text and shipping ETA boundaries

**Files:**
- Modify: `apps/api/src/fruit_agent/model_gateway/schemas.py`
- Modify: `apps/api/src/fruit_agent/copilot/service.py`
- Test: `apps/api/tests/unit/test_copilot_model_gateway.py`
- Test: `apps/api/tests/integration/test_copilot_api.py`

**Interfaces:**
- Consumes: `CopilotSKUFactClaims`, `ProductSKURead`, `CopilotCase`.
- Produces: complete claim validation and deterministic `_risk_tip`.

- [ ] **Step 1: Write failing schema and API tests**

Add a schema assertion that omitting `shipping_eta` raises `ValidationError`.
Add API assertions that SQL/non-null claim mismatches hand off and hostile
model `suggestion_text`/`risk_tip` containing a false price and `wxid` never
appear in the response, history, or persisted row.

- [ ] **Step 2: Verify RED**

Run:
`python -m pytest tests/unit/test_copilot_model_gateway.py tests/integration/test_copilot_api.py -k "shipping_eta or model_free_text" -q`

Expected: omitted `shipping_eta` is accepted, null mismatches are accepted, or
model `risk_tip` appears in persistence.

- [ ] **Step 3: Implement the minimal boundary**

Remove the Pydantic default from `shipping_eta`; compare normalized claim and
SQL values unconditionally; replace `draft.risk_tip` persistence with a fixed
mapping from controlled risk and intent.

- [ ] **Step 4: Verify GREEN**

Re-run the focused command and require all selected tests to pass.

### Task 2: Add deterministic intent templates and trusted knowledge

**Files:**
- Modify: `apps/api/src/fruit_agent/copilot/service.py`
- Test: `apps/api/tests/integration/test_copilot_api.py`

**Interfaces:**
- Consumes: case stage/intent, a verified `ProductSKURead`, the draft's
  referenced IDs, and the server-loaded `MerchantKnowledge` list.
- Produces: `_render_verified_suggestion(...) -> str`.

- [ ] **Step 1: Write failing template tests**

Add positive delivery, storage, gift, product/recommendation, and approved
knowledge-reference tests. Assert relevant trusted fields are present and
model prose is absent.

- [ ] **Step 2: Verify RED**

Run the new parametrized/template tests and confirm the current canonical-only
renderer lacks the intent-specific fields and approved excerpt.

- [ ] **Step 3: Implement deterministic rendering**

Render fixed copy per controlled intent. Intersect referenced IDs with loaded
knowledge before appending `已审核知识：{content}`. Never concatenate any model
text.

- [ ] **Step 4: Verify GREEN**

Re-run the focused template tests and require all to pass.

### Task 3: De-duplicate cards and verify the branch

**Files:**
- Modify: `apps/api/src/fruit_agent/copilot/service.py`
- Test: `apps/api/tests/integration/test_copilot_api.py`
- Create: `.superpowers/sdd/final-fix-report-4.md`

**Interfaces:**
- Consumes: validated suggestions in model order.
- Produces: at most one card per SKU, with distinct SKUs rendered separately.

- [ ] **Step 1: Write failing duplicate/distinct SKU tests**

Assert duplicate drafts for one SKU yield one card and different verified SKUs
yield different deterministic cards.

- [ ] **Step 2: Verify RED**

Run the two tests and confirm duplicate drafts currently yield duplicate cards.

- [ ] **Step 3: Implement stable de-duplication**

Keep the first valid draft for each SKU code in model order, cap the resulting
unique list at three, and use it for both validation and persistence.

- [ ] **Step 4: Verify focused and full suites**

Run focused copilot/schema tests, full backend pytest, Ruff, strict mypy,
Alembic head → base → head, frontend tests/lint/build, and `git diff --check`.

- [ ] **Step 5: Document and commit**

Record RED/GREEN evidence and exact verification output in report 4, commit the
implementation, then commit the report.
