# RouteDeck Headed Navigation Video Design

**Status:** Approved design awaiting written-spec review
**Date:** 2026-07-17

## Goal

Produce one high-quality human checkout video in which the real browser address bar remains visible, the Navgraph stays open beside the application without covering chat, and no full-document navigation occurs after the initial storefront load.

## Scope

This slice changes desktop Navgraph presentation and the dedicated human-checkout recording harness. It does not change RouteDeck runtime semantics, Medusa commerce behavior, agent prompting, checkout operations, mobile Navgraph behavior, or session authorization.

## Desktop layout

On desktop, `.buyer-workspace` becomes a two-column layout with the agent shell in `minmax(0, 1fr)` and the Navgraph in an automatic-width right column. The collapsed Navgraph remains a narrow rail. When expanded, it grows within the grid and the chat column shrinks; it never overlays or obscures chat, surfaces, review controls, or the composer.

The expanded panel remains capped at the existing readable maximum width. The agent shell keeps a minimum usable width and independently scrolls its conversation/surface region. At the existing mobile breakpoint, the Navgraph remains a fixed overlay because a persistent two-column layout is not viable on a narrow screen.

The product continues to open the Navgraph on user request. The recording opens it once immediately after the initial app is ready and never closes it. This keeps ordinary product behavior intact while making the Navgraph permanent for the recorded story.

## Navigation story

The story starts with one initial navigation to `/`. After bootstrap:

1. Open the Navgraph and keep it open.
2. Ask the curious newcomer questions already used by the approved human story.
3. Reach `/products` through the agent's RouteDeck navigation.
4. Open the visible product by clicking its rendered link rather than calling `page.goto`.
5. Select a visible variant, adjust quantity, and reach `/cart` through normal UI and agent navigation.
6. Complete contact, delivery, payment, review, approval, and confirmation through the existing surfaces.
7. Keep `proveCheckoutPersistence: false`; do not reload delivery, review, or confirmation.

Every URL after `/` is produced by RouteDeck's SPA route controller or a normal rendered UI action. The expected trace contains one initial `goto`, zero `reload` actions, and zero later `goto` actions.

The recording pauses briefly after important route transitions so the real browser address bar visibly shows the public product path, cart path, session-bound checkout paths, and order-confirmation path. The pause changes only presentation timing in the dedicated recording test.

## Navgraph evidence

At each story stage, the test asserts that the already-open Navgraph reports the expected current node and that exactly one graph node has `data-node-tone="current"`. It does not close or reopen the panel. The visible sequence covers:

- `buyer.home`;
- `catalog.browse`;
- `catalog.product`;
- `cart.summary`;
- `checkout.contact`;
- `checkout.delivery`;
- `checkout.payment`;
- `checkout.review` and approval;
- `orders.confirmation`.

## Recording architecture

The existing Playwright story remains the interaction driver, but a dedicated headed configuration launches installed Chrome maximized with browser chrome visible. Xbox Game Bar records the actual Chrome window at the active display's native high resolution. This is intentionally separate from Playwright's viewport-only WebM recording, which cannot show the real address bar.

The recorder starts only after the headed Chrome window exists and stops immediately after the Playwright story completes. The final MP4 is copied into a timestamped directory under `artifacts/` together with the Playwright JSON report, trace, final screenshot, and a concise validation report.

No simulated address bar or in-page URL strip is permitted. If Game Bar omits browser chrome, records the wrong window, produces unreadable output, or cannot record Chrome, the run fails explicitly and no substitute video is presented as successful.

## Data and security

The video uses the local demo stack and isolated E2E buyer data. Checkout resume handles may be visible in the localhost address bar because visible deeplinks are an explicit requirement. They remain bound to the same guest cookie and local session; the URL alone does not authorize another browser. Private checkout form values must not be deliberately focused, enlarged, or reproduced in the report.

No API keys, cookies, request headers, local files, browser storage, or developer tools appear in the recording.

## Targeted verification

Testing is limited to the immediate change and requested evidence:

1. A focused Navgraph/app-shell test preserves collapsed-by-default and expanded behavior.
2. Frontend and E2E TypeScript checks pass.
3. Browser-plugin QA at desktop width verifies the open Navgraph occupies layout space, chat remains visible and usable, no framework overlay appears, and the console is clean.
4. The headed live checkout runs once with zero retries.
5. Trace audit proves one initial `goto`, zero later `goto`, and zero reloads.
6. Video metadata and a visual review prove real Chrome browser chrome, readable address-bar changes, permanently open Navgraph, visible chat, high-resolution output, and final `orders.confirmation` state.

No broad regression or duplicate full-checkout run is required.

## Completion criteria

The slice is complete only when:

- desktop Navgraph expansion no longer overlays chat;
- mobile overlay behavior is unchanged;
- Navgraph remains open throughout the recorded story;
- all post-bootstrap navigation is SPA navigation;
- the actual address bar visibly changes through the important deeplinks;
- the trace contains no reload and no later document navigation;
- the live checkout reaches a visible order confirmation;
- the high-quality video and validation artifacts are linked in the final report;
- no git operation has occurred without a separate explicit request.
