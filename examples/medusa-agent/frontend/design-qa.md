# Medusa Agent Frontend QA

This note describes the current frontend implementation. It is not release
evidence; only a current sanitized bundle produced by
`examples/medusa-agent/scripts/release-verify.ps1` can claim the complete buyer
flow passed.

## Product Direction

The buyer experience is conversation-led, with projected commerce surfaces in
the main pane and RouteDeck status in a secondary rail. Product UI never calls
Medusa Store APIs directly. It renders the public RouteDeck projection and
dispatches only currently legal RouteDeck operations.

The implemented guest flow is:

```text
welcome -> products -> product detail -> cart
        -> contact -> shipping -> payment -> review -> confirmation
```

The visual hierarchy keeps these responsibilities distinct:

- the main pane owns buyer surfaces, conversation, and the composer;
- the header owns buyer navigation and exact back/forward/cancel controls;
- the status rail exposes the current RouteDeck node, versions, review, and
  public-safe failure state;
- private checkout fields remain inside the dedicated private-form channel;
- review acceptance remains disabled until the private delivery summary is
  authoritatively rehydrated.

## Surface And Recovery Checks

- Product cards, variants, prices, cart lines, shipping options, payment
  providers, and confirmation facts come from typed backend projection data.
- Optimistic browser state is never treated as committed commerce state.
- Reload and browser-history restoration use confirmed RouteDeck entry
  identities rather than URL heuristics.
- Outcome-unknown mutations retain the exact request identity for explicit
  retry or resynchronization.
- Session creation, missing/expired sessions, SSE resets, interrupted chat
  turns, order reconciliation, and unavailable dependencies render explicit
  recovery states.
- The component registry is product-owned while the host, navigation, review,
  private-form, status, and read-only inspector primitives are RouteDeck-owned.

## Automated QA Boundary

Frontend unit/component tests cover the application shell, catalog, cart,
checkout, private forms, review authority, chat reliability, bootstrap
recovery, and exact routing/session behavior. The Playwright release lane owns
desktop and narrow-viewport browser proof, direct-Store-API network rejection,
full guest checkout, persistence across API restart, and the separate live
model smoke.

The authoritative commands and current proof boundaries are maintained in
[`../../../test_index/README.md`](../../../test_index/README.md).
