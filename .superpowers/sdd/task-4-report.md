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
- `apps/web/tests/app-shell.test.tsx`
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
3. Independent-review regressions:
   - Command:
     `node node_modules/vitest/vitest.mjs run
     tests/copilot-workspace.test.tsx -t
     "requires unsaved|keeps recorded|rotates the action" --reporter=dot`
   - Result before remediation: `3 failed`.
   - The failures proved that unsaved edits could be adopted, a successful
   event could be misreported as failed when its background refresh failed,
   and repeated outcomes reused one idempotency key.
4. Parent-review regressions:
   - Successful case creation followed by a failed list refresh rendered the
     generic generation failure. The focused test failed with
     `Expected: 工单已生成，但近期工单刷新失败; Received:
     生成失败，请稍后重试`.
   - Two successful suggestion adoptions produced identical idempotency keys.
   - A surrounding-whitespace edit left adoption enabled instead of marking
     the raw text dirty.
   - Advancing fake time beyond `valid_until` left knowledge freshness at
     `有效`.
   - The active navigation link had no `aria-current="page"`.
   - A failed initial recent-case request also rendered
     `暂无近期工单。` and exposed no list retry.
   - Each regression was run and observed failing independently before its
     implementation change.

## GREEN evidence

- First focused Task 4 result: `2` files, `16` tests passed.
- Final full web result after the independent-review regressions:
  `4` files, `27` tests passed, zero unhandled errors.
- Covered behavior:
  - successful suggestions and maximum-three rendering;
  - mandatory handoff and reasons;
  - exact suggestion edit request;
  - clipboard-before-event adoption;
  - copy failure and event failure retry without false success;
  - mandatory save-before-adopt for dirty suggestion edits;
  - stable adoption and per-action-instance idempotency keys;
  - adoption-key reuse across copy/event failures and rotation after each
    successful adoption;
  - exact raw-text dirty checks and backend-returned persisted copy text;
  - successful event status preserved across background refresh failures,
    with an explicit refresh retry;
  - successful case POSTs preserved when only the subsequent recent-case list
    refresh fails, with a list-only retry and no duplicate POST;
  - expandable citation snapshots;
  - payment, refund, complaint, and close events;
  - detail/recent-case refresh and current-session timeline;
  - loading/error announcements;
  - distinct initial recent-case error/empty states and list-only retry;
  - active-link `aria-current="page"` semantics;
  - live knowledge provenance, owner, review status, dates, freshness, and
    content;
  - create/edit/review wire shapes;
  - visible reset-to-draft status;
  - denied knowledge edit retained for correction and retry.
  - minute-by-minute knowledge freshness transitions with interval cleanup.

## Final verification

All commands used `CI=true`, the pinned Node runtime at
`C:\Users\15977\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin`,
and the pinned pnpm fallback.

- `pnpm run test -- --reporter=dot` —
  `4 passed` test files, `27 passed` tests.
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
AB2F7BEA472341239AEFD8EB7EFCA4D31B41F689C4706A754F07C6117AB96155  apps/web/components/app-shell.tsx
4374CF36124FA1BA9FB9D4FA0CF5A97172376DA616E09234622FC17F22C6F321  apps/web/components/copilot/copilot-workspace.tsx
059DA211D84BD1C4ABC9409F85F6843CF818064A042FF3FE447766A38E02F086  apps/web/components/copilot/suggestion-card.tsx
8EC2F3A84C16779793233BEE0E42EE2DAE70B2EF3AAF7BADCB5CC333D31542EC  apps/web/components/knowledge/knowledge-table.tsx
4FDD01788A2FA2FA13799FBF012C1CA35A3D8C0C54486B76AB423FA78F0127DF  apps/web/components/knowledge/knowledge-workspace.tsx
D99024EEF02050A994CD1E3FFCD142A9D8595365DD3E78159B64CA1D6C8ED3A0  apps/web/tests/app-shell.test.tsx
0ECCC9A21C51FD313C1E2FBD19183508481186866FD00D4C42D5965698053C07  apps/web/tests/copilot-workspace.test.tsx
043CAE2FF823CF510E28D0058F7833AB04F7485F083F58F3A2A8D9D3C5BD8CA8  apps/web/tests/knowledge-workspace.test.tsx
092DBDCD0A47393455A69D454D999E7AAA626266EDF026169EA6AE3D41F80D34  docs/design/foundation-workspace-concept.png
```

## Concerns

- Historical outcome events cannot be reloaded after navigation because Tasks
  1–3 do not expose a `GET` event-timeline endpoint. The UI truthfully labels
  the available list “本次操作记录” and does not invent persisted history.
- Production browser screenshots were taken without a running authenticated
  backend. Populated and permission/error states were rendered and exercised
  through the complete Testing Library fixtures instead.
