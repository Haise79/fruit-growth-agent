# Task 4 — Copilot workspace and dynamic knowledge UI

## Scope

Implemented the production-oriented `/copilot` workflow, replaced the static
`/knowledge` rows with the live knowledge-management APIs, added exact typed
frontend contracts/helpers, navigation, responsive green/white workspace
styles, and Testing Library coverage.

Base revision:
`33072bf78b2c8032bcb6929b462cae30e9d14352`.

No backend schemas, migrations, routes, or services were changed.

## Exact API mapping

- Copilot case create/list/detail, suggestion edit, and outcome events use the
  exact Task 2–3 paths and wire names.
- Knowledge list/create/update/review uses the exact Task 1 paths and wire
  names.
- The backend exposes no latency field, so the UI reports measured client
  request latency.
- The backend exposes no separate handoff/degraded reason field, so the UI
  renders `risk_reasons`.
- The backend exposes no outcome-event list endpoint. The timeline therefore
  displays events returned during the current page session, while every
  successful action refreshes both case detail and recent cases.

## Changed files

- `.superpowers/sdd/task-4-report.md`
- `apps/web/app/copilot/page.tsx`
- `apps/web/app/globals.css`
- `apps/web/app/knowledge/page.tsx`
- `apps/web/components/app-shell.tsx`
- `apps/web/components/copilot/case-form.tsx`
- `apps/web/components/copilot/case-panel.tsx`
- `apps/web/components/copilot/copilot-workspace.tsx`
- `apps/web/components/copilot/labels.ts`
- `apps/web/components/copilot/suggestion-card.tsx`
- `apps/web/components/knowledge/knowledge-form.tsx`
- `apps/web/components/knowledge/knowledge-table.tsx`
- `apps/web/components/knowledge/knowledge-workspace.tsx`
- `apps/web/lib/api.ts`
- `apps/web/lib/types.ts`
- `apps/web/tests/copilot-workspace.test.tsx`
- `apps/web/tests/knowledge-workspace.test.tsx`
- `apps/web/tests/setup.ts`

## RED evidence

1. Initial Task 4 suites:
   - Command:
     `node node_modules/vitest/vitest.mjs run
     tests/copilot-workspace.test.tsx tests/knowledge-workspace.test.tsx`
   - Result: `2 failed`, `no tests` collected.
   - Both suites failed for the intended reason: the wished-for
     `CopilotWorkspace` and `KnowledgeWorkspace` modules did not exist.
2. Retryable knowledge-edit regression:
   - Command:
     `pnpm run test -- tests/knowledge-workspace.test.tsx -t
     "keeps a failed edit available for correction and retry"`
   - The behavior assertions passed, but Vitest exited `1` with one unhandled
     rejection from `knowledge update failed`.
   - This proved that a denied edit showed an error but leaked a rejected
     promise. The fix returns an explicit success boolean and keeps the editor
     open for retry.

## GREEN evidence

- First focused Task 4 result: `2` files, `16` tests passed.
- Final full web result after the edit-retry regression:
  `3` files, `18` tests passed, zero unhandled errors.
- Covered behavior:
  - successful suggestions and maximum-three rendering;
  - mandatory handoff and reasons;
  - exact suggestion edit request;
  - clipboard-before-event adoption;
  - copy failure and event failure retry without false success;
  - stable adoption and per-action idempotency keys;
  - expandable citation snapshots;
  - payment, refund, complaint, and close events;
  - detail/recent-case refresh and current-session timeline;
  - loading/error announcements;
  - live knowledge provenance, owner, review status, dates, freshness, and
    content;
  - create/edit/review wire shapes;
  - visible reset-to-draft status;
  - denied knowledge edit retained for correction and retry.

## Final verification

All commands used `CI=true`, the pinned Node runtime at
`C:\Users\15977\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin`,
and the pinned pnpm fallback.

- `pnpm run test -- --reporter=dot` —
  `3 passed` test files, `18 passed` tests.
- `pnpm run lint` — exit `0`, no ESLint warnings or errors.
- `pnpm run build` — exit `0`; TypeScript passed and Next 16.2.10 statically
  generated `/copilot` and `/knowledge`.
- `git diff --check` — no whitespace errors.
- `next-env.d.ts` SHA-256 remained
  `7B550DDA9686C16F36A17BF9051D5DBF31E98555B30D114AC49FC49A1E712651`
  before and after both production builds.
- `.next` remains ignored and is not part of the commit.

## UX, accessibility, and visual self-review

The accepted visual source was
`docs/design/foundation-workspace-concept.png`. The built-in browser was not
available in this task context, so local production pages were captured with
headless Chrome as the documented fallback.

- Desktop capture: 1440×1000.
- Mobile capture: Chrome DevTools device emulation at 390×844.
- The mobile runtime reported `innerWidth: 390` and `scrollWidth: 390`, proving
  there is no document-level horizontal overflow.
- Both the source concept and latest desktop/mobile captures were inspected
  with `view_image`.

Fidelity ledger:

1. **Shell:** fixed left rail, white workspace, green active navigation, and
   thin gray separators match the foundation concept.
2. **Container model:** the Copilot result area uses rails, rows, and an
   operational sidebar; the knowledge page remains table-led. No decorative
   gradients, bento grids, or ornamental cards were added.
3. **Typography:** headings, labels, controls, tables, status text, and mobile
   line breaks use the existing system type stack and deliberate control
   sizes.
4. **Palette:** true-white surfaces, existing dark green, mint active state,
   gray rules, and red error state are preserved.
5. **Responsive behavior:** the 300px recent-case rail moves below the primary
   workflow; classifications and SKU inputs become one column; navigation
   remains keyboard-scrollable.
6. **Interaction:** editable suggestions, citation disclosure, copy/adopt,
   outcome controls, create/edit/review, retry states, and recent-case
   selection all have visible focus and real local state.
7. **Accessibility:** semantic labels/fieldsets/tables/details, keyboard-native
   buttons, `aria-current`, visible `:focus-visible`, status/error live
   regions, screen-reader-only labels, and reduced-motion-safe transitions are
   present.

Above-the-fold copy diff: only Task 4-required labels and safety clarification
were added. There is no send control and no unapproved decorative eyebrow,
badge, metric, or marketing copy.

The implementation was faithfully verified against the existing foundation
design. No fixable visual mismatch remained in the inspected desktop or true
390px mobile states.

## SHA-256 hashes

```text
E030B05C98C23DC911CCB50962BFC27998AF12ED0F88C03F4AF408D8BF7B272A  apps/web/lib/types.ts
770486E477767C72867CA03AA5C76141727C0B513409FBF76AF42299F5749A2F  apps/web/lib/api.ts
70B55666808B445FBCAE238A055077CA99204BC40F110BBF58A94A3E96047C0C  apps/web/components/copilot/copilot-workspace.tsx
4FDD01788A2FA2FA13799FBF012C1CA35A3D8C0C54486B76AB423FA78F0127DF  apps/web/components/knowledge/knowledge-workspace.tsx
93318A448C851D9A0DD1D3864F95D72354B7739371C490370F228F4DC05112D4  apps/web/tests/copilot-workspace.test.tsx
C2FEB6FE87BF517E8F7895DC2F26271DB00C1904675C136AF064445247EA9859  apps/web/tests/knowledge-workspace.test.tsx
092DBDCD0A47393455A69D454D999E7AAA626266EDF026169EA6AE3D41F80D34  docs/design/foundation-workspace-concept.png
```

## Concerns

- Historical outcome events cannot be reloaded after navigation because Tasks
  1–3 do not expose a `GET` event-timeline endpoint. The UI truthfully labels
  the available list “本次操作记录” and does not invent persisted history.
- Production browser screenshots were taken without a running authenticated
  backend. Populated and permission/error states were rendered and exercised
  through the complete Testing Library fixtures instead.
