# Medusa Agent UI User-Story Validation

Date: 2026-07-14  
Runtime: local Windows Docker Compose stack; frontend `http://127.0.0.1:5198/`,
agent `http://127.0.0.1:8098/`, Medusa `http://127.0.0.1:9100/`.

This is a focused, real-browser validation of the standalone reference app.
It drives the rendered buyer UI against the already-running local stack. It
does not substitute a fake model, catalog, cart, or payment path.

## User stories

| ID | Buyer journey | User actions | Expected observable result |
| --- | --- | --- | --- |
| CHAT-01 | Conversational discovery | Open the lounge, say `Hello`, then ask to browse products. | The system-prompt greeting is shown, the turn visibly progresses from thinking to streaming to finalized, `Hello` remains at home, and the browse request moves the compiled session to Products. |
| SURFACE-01 | Surface-led guest purchase | Use the `Browse products` suggested action, open a real product, select a real variant, add it to cart, then complete checkout and approve the order. | Every UI affordance resolves through RouteDeck, the real Medusa cart/order lifecycle completes, and the confirmation page is session-bound. |
| HYBRID-01 | Agent-guided purchase | Ask the agent to browse products, then use product, cart, and checkout surfaces to complete the purchase. | The chat tool call and all subsequent surfaces converge on the same supervised RouteDeck runner; the final order is a verified Medusa order. |

## Monitoring contract

Each story is observed at these boundaries:

| Component | Evidence required |
| --- | --- |
| Browser/UI | Rendered Chromium UI has no page errors, unexpected HTTP failures, or visible chat error. |
| Chat transport | A real RouteDeck-owned `POST /api/routedeck/chat` returns `text/event-stream`; CHAT-01 also observes the user-visible thinking/streaming/finalized sequence. |
| RouteDeck | A buyer session is created, UI operations post to `/api/routedeck/dispatch`, and the Navgraph reports `data-status="live"` throughout the interaction. |
| Browser-to-data boundary | The browser makes no Medusa `/store/*` or port `9100` request. The product backend, not the browser, owns Store API access. |
| Agent and Medusa runtime | Readiness/health endpoints are checked before and after the runs; container status and logs are reviewed for new errors. |
| Projection transport | `GET /api/routedeck/events` is the authoritative state SSE. `VITE_USE_POLLING=true` configures only Vite file watching inside Docker; it does not replace RouteDeck SSE with HTTP polling. |

## Test mapping

| Story | UI test |
| --- | --- |
| CHAT-01 | `e2e/live-model.spec.ts` (both live-model cases) |
| SURFACE-01 | `e2e/buyer-flow.spec.ts` |
| HYBRID-01 | `e2e/user-stories.spec.ts` |

## Run record

### Preflight and component monitoring

Before and after the browser runs:

- frontend `GET /` returned `200`;
- agent `GET /api/medusa-agent/ready` returned `200` with `{"status":"ready"}`;
- Medusa `GET /health` returned `200` with `OK`;
- RouteDeck frontend, agent API, Medusa, Redis, and PostgreSQL containers were
  all Docker-healthy.

The browser suite installs an automatic monitor that fails any story when the
rendered UI has a page/runtime error, unexpected HTTP failure, or a browser
request to Medusa `/store/*` or port `9100`. All passing stories met that
monitoring contract. The hybrid test additionally asserted successful agent
chat, RouteDeck session creation, RouteDeck dispatches, and RouteDeck
projection synchronization.

For the post-fix focused run, agent API, Medusa, and frontend logs each
contained zero `409`, `5xx`, `ERROR`, or traceback lines in the run window.
All five protected local containers remained healthy after the stories.

### Commands and outcomes

```powershell
pnpm --dir examples/medusa-agent/e2e typecheck
pnpm --dir examples/medusa-agent/e2e exec playwright test --config playwright.config.ts --project=desktop-chromium live-model.spec.ts
pnpm --dir examples/medusa-agent/e2e exec playwright test --config playwright.config.ts --project=desktop-chromium buyer-flow.spec.ts
pnpm --dir examples/medusa-agent/e2e exec playwright test --config playwright.config.ts --project=desktop-chromium user-stories.spec.ts
```

| Story | Result | Proof |
| --- | --- | --- |
| CHAT-01 | Passed | Both live-model UI cases passed: the system-prompt greeting and `Hello` stayed at home, then the real model navigated to Products. The UI timeline observed thinking, streaming, and finalized states in order; chat returned `text/event-stream`. |
| SURFACE-01 | Passed | The rendered UI completed a real Medusa guest cart, checkout, review/approval, order confirmation, reload, and anonymous-session denial check. |
| HYBRID-01 | Passed | The real model opened Products and the test attempted the product click immediately when the Products surface appeared, without waiting for the assistant to finalize. RouteDeck held the affordance until the chat interaction became idle, then the buyer completed product, cart, checkout, review, and confirmation against real Medusa with no `409`. |

### Resolved finding: authoritative interaction handshake

The earlier exploratory race was caused by a server-owned chat lease that was
not represented in the public projection. The product surface could therefore
become actionable while the parent chat turn still owned the session.

RouteDeck now commits `interaction={phase: active, owner: chat}` and emits
`turn_started` before invoking the product agent driver. The existing state SSE
causes the browser to fetch the advanced projection; generic surface and
suggested-action primitives remain inert while that interaction is active.
Finalization, interruption, and review staging project the interaction back to
idle. The assistant token stream remains a rendering channel, not a second
state authority.

The regression story deliberately removed its former wait for the finalized
assistant. It passed the full real-Medusa purchase, and post-run monitoring
found no `409` or component error.

The final verification run against the restarted, refactored agent process
passed HYBRID-01 in 23.3 seconds. All five local services remained healthy and
the agent API, Medusa, and frontend each produced zero matching
`409`/`5xx`/`ERROR`/traceback log lines in that run window.

### Validation environment note

The in-app browser connector could not initialize in this local Codex runtime
because its Node bootstrap throws `Cannot redefine property: process` before it
can attach to a tab. The stories above were therefore driven through the
repository's Playwright Desktop Chromium suite against the live local frontend,
not a mocked DOM or API client.
