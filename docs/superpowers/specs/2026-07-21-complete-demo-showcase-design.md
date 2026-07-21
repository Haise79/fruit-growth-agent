# Complete Demo Showcase Design

**Date:** 2026-07-21

## Goal

Provide a complete, repeatable local demonstration of the existing Fruit Growth Agent product. A non-technical user must be able to enter a development-only demo session, browse every current workspace, and see a coherent fruit-commerce story backed by the real FastAPI API and PostgreSQL database.

The showcase covers the current product scope only: overview, members, product import, trusted knowledge, approvals, and customer-service copilot. It does not simulate or enable real Douyin, Feige, refund, compensation, price, inventory, or publishing execution.

## Recommended Approach

Use a real PostgreSQL-backed seed workflow plus a development-only demo sign-in. This gives the browser UI authentic API, permission, audit, RLS, knowledge, approval, and copilot behavior while keeping production authentication closed.

Alternatives rejected:

- Direct database seeding without a demo sign-in leaves a non-technical user responsible for generating and pasting JWTs.
- Frontend-only fixture data cannot demonstrate backend authorization, persistence, tenant isolation, auditing, or safety behavior.

## Demo Story

The demo tenant is `果序生鲜（华东）`, a regional fruit merchant preparing and supporting several seasonal products.

The seeded scenario includes:

- Four active members representing owner, operator, support, and implementer responsibilities.
- Six SKUs with realistic names, prices, inventory, origin, variety, ripeness, specification, weight, sales region, shipping estimate, freshness, and source metadata.
- Eight knowledge records spanning approved, draft, rejected, expired, and conflicting states.
- Four approval requests spanning pending, approved, and rejected decisions.
- Five copilot cases demonstrating:
  - a normal product question with grounded reply suggestions;
  - a complaint requiring human handoff;
  - a refund-related high-risk request;
  - expired or conflicting evidence causing a fail-closed response;
  - recursive masking of phone or address information.
- Outcome events spanning suggestion adoption, rejection, payment, complaint, and case closure where compatible with the domain state machine.

All customer content is synthetic. No real person, phone number, address, order, credential, or merchant secret is used.

## Components

### Idempotent Seed Command

A repository-owned Python command creates or refreshes the demo tenant using stable identifiers. It may update records that belong to the dedicated demo tenant, but it must not delete or modify any other tenant.

The command:

1. Verifies that the configured environment is development.
2. Applies the current Alembic migrations.
3. Creates the demo tenant and four users/members.
4. Creates products, knowledge, approvals, cases, suggestions, citations, and outcome events in dependency order.
5. Generates a local RS256 signing key pair when the demo key files do not exist.
6. Emits the non-secret local URLs and a clear completion summary.

Repeated runs converge to the same logical dataset instead of duplicating records. Existing non-demo tenant data remains untouched.

### Development-Only Demo Authentication

Add an explicit demo-mode setting that defaults to disabled. A demo-session API is available only when both conditions hold:

- `ENVIRONMENT=development`
- `DEMO_MODE=true`

When enabled, the endpoint returns a short-lived RS256 JWT for one seeded demo user. The endpoint supports selecting the seeded role so the permissions can be demonstrated. It never accepts an arbitrary tenant or user ID.

When either condition is false, the endpoint behaves as unavailable. Production behavior and the normal JWT verifier remain unchanged.

### Demo Entry Screen

The management UI shows a compact “进入演示” panel only when `NEXT_PUBLIC_DEMO_MODE=true`. The user chooses one of the seeded roles, requests a short-lived demo session, stores the returned token using the existing local-storage convention, and enters the workspace.

The panel clearly labels the environment as synthetic local demo data. It does not embed a permanent token, private key, or password in the frontend bundle.

### Showcase Navigation

Existing routes remain the source of truth:

- `/` — capability overview and demo identity
- `/members` — seeded role membership
- `/imports` — a ready-to-use CSV example and validation behavior
- `/knowledge` — lifecycle, freshness, provenance, and conflict examples
- `/approvals` — pending, approved, and rejected safety decisions
- `/copilot` — grounded suggestions, handoff, redaction, history, and outcomes

Only small demo guidance may be added. The product views continue to use the real APIs and existing components.

## Data and Security Boundaries

- The demo seed is scoped to one stable demo tenant ID.
- Tenant-owned reads and writes keep explicit tenant filters and PostgreSQL RLS.
- Demo authentication is disabled by default and fails closed outside development.
- The signing private key remains local and gitignored.
- Tokens are short-lived and contain only the seeded tenant, seeded user, audience, and expiry claims.
- Synthetic sensitive-looking values are masked before persistence and model/provider invocation.
- High-risk requests create handoff or approval states and never execute commerce actions.
- Seed output and application logs must not print the private key or full JWT.

## Data Flow

1. Developer enables local demo mode and starts PostgreSQL.
2. Seed command migrates the database and converges the demo dataset.
3. API and web applications start normally.
4. User opens the demo entry panel and selects a seeded role.
5. Web requests a short-lived demo token from the development-only endpoint.
6. Existing API helpers attach the token to real requests.
7. Each workspace reads or mutates the seeded tenant through normal permission, RLS, audit, safety, and validation paths.

## Error Handling

- Missing database: the seed command exits with a direct instruction to start PostgreSQL.
- Database at an incompatible migration: the command reports the current and expected revision without stamping or destroying data.
- Demo mode disabled: demo-session endpoint returns 404 so the capability is not advertised.
- Missing demo seed: demo-session endpoint returns a clear development-only setup error.
- Seed collision outside the stable demo tenant: abort without modifying the conflicting record.
- Partial seed failure: use a transaction so no incomplete demo dataset is committed.
- Frontend session failure: keep the entry panel visible with a retryable Chinese error message.

## Verification

Implementation is complete only after all of the following pass:

- Seed command can run twice with stable counts and identifiers.
- Non-demo tenant fixtures remain unchanged after seeding.
- Demo-session endpoint is unavailable when demo mode is disabled or environment is not development.
- Each seeded role receives only its declared permissions.
- API tests cover members, knowledge states, approvals, copilot cases, citations, redaction, and outcomes in the seeded scenario.
- Frontend tests cover demo entry success, failure, role selection, and token storage without embedding secrets.
- Existing backend suite, security suite, Ruff, mypy, frontend Vitest, ESLint, and Next.js production build pass.
- A smoke check opens every current route and confirms its primary API returns demo data.

## Operational Use

The finished workflow will expose one documented command for seeding and concise commands for starting API and web. The final handoff includes:

- local management URL;
- local API documentation URL;
- available demo roles;
- a guided route-by-route demonstration script;
- instructions for refreshing only the dedicated demo dataset.

## Out of Scope

- Real Douyin or Feige authorization and messaging.
- Real refunds, compensation, price changes, inventory changes, or content publishing.
- Production user registration, password authentication, or account recovery.
- Short-video Agent, content calendar, growth dashboard, billing, and production deployment.
- Seeding or modifying any tenant other than the dedicated local demo tenant.
