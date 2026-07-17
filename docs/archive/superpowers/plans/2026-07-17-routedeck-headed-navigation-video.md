# RouteDeck Headed Navigation Video Implementation Plan

> **Execution note:** The user approved inline execution in the current checkout. No worktree, commit, or other Git operation is authorized for this slice.

**Goal:** Record one real Chrome checkout with the address bar visible, a permanently open docked Navgraph, and zero full-document navigation after the initial storefront load.

**Architecture:** Desktop layout responsibility stays in the Medusa example frontend: the buyer workspace allocates separate grid columns to the agent shell and Navgraph. The dedicated E2E story drives only public UI and RouteDeck SPA navigation. A separate headed Playwright configuration exposes a maximized Chrome window while Xbox Game Bar records the entire window after explicit user approval.

**Stack:** React, CSS Grid, TypeScript, Playwright, installed Google Chrome, Xbox Game Bar.

---

## Task 1: Lock the desktop layout contract

**Files:**
- Create: `examples/medusa-agent/e2e/navgraph-layout.spec.ts`
- Modify: `examples/medusa-agent/frontend/src/app/app.css`
- Modify: `examples/medusa-agent/frontend/src/ui/navgraph-sidebar.css`

1. Add a focused desktop Playwright test that opens Navgraph and measures the agent-shell and sidebar bounds.
2. Assert that the expanded sidebar starts at or after the agent shell's right edge and that the composer remains visible.
3. Run the test once against the current fixed sidebar and confirm the overlap assertion fails.
4. Convert `.buyer-workspace` to a two-column grid and make the desktop sidebar a normal-flow grid child.
5. Restore the existing fixed-overlay behavior explicitly below the mobile breakpoint.
6. Re-run only the focused layout test and confirm it passes.

Command:

```powershell
pnpm --dir examples/medusa-agent/e2e exec playwright test navgraph-layout.spec.ts --config playwright.config.ts --project=desktop-chromium
```

## Task 2: Make the human checkout one continuous SPA story

**Files:**
- Modify: `examples/medusa-agent/e2e/human-checkout-flow.spec.ts`

1. Keep Navgraph open after the first `buyer.home` assertion and remove all close/reopen calls.
2. Replace the product `page.goto(...)` with a click on the rendered product link.
3. Remove the delivery reload while retaining resume-handle and deeplink assertions.
4. Add presentation-only pauses after visible route/node transitions.
5. Add explicit ready/complete console gates so external recording can start after Chrome exists and stop after confirmation.
6. Statically verify the story contains exactly one `goto` and no `reload` call.

## Task 3: Add the real-window recording harness

**Files:**
- Create: `examples/medusa-agent/e2e/headed-checkout-video.playwright.config.ts`
- Modify: `examples/medusa-agent/e2e/package.json`

1. Add a one-worker, zero-retry, headed Playwright configuration restricted to the human checkout story.
2. Launch the installed Chrome channel maximized with `viewport: null`; disable Playwright video because Game Bar owns whole-window capture.
3. Require an explicit artifact directory and retain trace, screenshot, and JSON report there.
4. Add a package script for the headed recording run.

## Task 4: Verify readiness without consuming the final checkout

**Files:**
- Verify only the files above and their immediate frontend/E2E type boundaries.

1. Run the focused desktop layout test.
2. Run frontend and E2E TypeScript checks.
3. Audit the human story source for one initial navigation and zero reloads.
4. Do not run the full live checkout and do not take visible system control.
5. Pause and ask the user for `go` before launching headed Chrome or starting Xbox Game Bar.

Commands:

```powershell
pnpm --dir examples/medusa-agent/frontend typecheck
pnpm --dir examples/medusa-agent/e2e typecheck
rg -n "page\.goto|checkoutPage\.goto|page\.reload|checkoutPage\.reload" examples/medusa-agent/e2e/human-checkout-flow.spec.ts
```

## Task 5: Record and validate after explicit `go`

1. Launch the headed story with `ROUTEDECK_PRESENTATION_RECORDING=1` and a timestamped artifact directory.
2. When `ROUTEDECK_RECORDING_WINDOW_READY` appears, focus Chrome and start Xbox Game Bar recording.
3. Let Playwright complete the full live checkout without interference.
4. When `ROUTEDECK_RECORDING_COMPLETE` appears, stop recording and copy the new MP4 into the artifact directory.
5. Verify the order-confirmation result, trace navigation counts, video resolution, real browser chrome, readable deeplinks, and continuously visible Navgraph/chat.
6. Deliver the MP4 and concise findings report; fail explicitly if whole-window capture is not valid.
