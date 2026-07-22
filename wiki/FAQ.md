# FAQ

## Is RouteDeck an agent framework?

Not in the usual sense. It does not own prompts, models, reasoning topology, or
product tools. It owns durable application interaction state and supervises
semantic operations proposed by agents and user interfaces.

## Does RouteDeck replace LangGraph?

No. The RouteDeck navgraph maps product locations and legal operations. A
product LangGraph maps model/tool orchestration. The optional adapter connects
them while keeping their authorities separate.

## Does RouteDeck call my API or database?

Your product handler does. RouteDeck checks the declared context, guard,
review, request identity, and version, invokes the allowed handler, then
commits the typed result/effects and public events.

## Can the UI update RouteDeck state optimistically?

It can show component-local pending presentation, but optimistic state is not
canonical. The authoritative browser store confirms only server projection and
ordered events.

## Why use opaque handles instead of product IDs?

Handles prevent a browser or model from carrying a real ID outside the exact
session, operation, entity kind, node, allowlist, and version where that entity
is currently permitted.

## Where do private form values go?

Into encrypted server-side blobs through a no-store private-form channel. They
do not enter public projection, events, inspection, frontend contracts, or
model context.

## What happens if a network response is lost?

For mutations, the client treats the outcome as potentially unknown, retains
the exact request ID and payload, and requires exact replay or explicit
abandonment/resync. It does not silently generate a new ID.

## Does RouteDeck automatically retry external writes?

No. If delivery was possibly sent, RouteDeck records an outcome-unknown state
and exposes a declared product reconciliation operation.

## Does RouteDeck provide authentication or multi-session accounts?

No. It requires a host-owned session selector. The product authenticates and
authorizes an opaque session handle before returning one internal session ID.
The Medusa demo uses explicit guest-cookie mode.

## Are the packages on PyPI or npm?

Not yet as of the current alpha documentation. Install from the public source
checkout until a published version is recorded in the
[changelog](https://github.com/saastoagent/routedeck/blob/main/CHANGELOG.md).

## Is the Medusa demo fake data?

It is an explicitly isolated local reference application that uses the real
local Medusa Store API and protected demo seed. It does not silently substitute
fixtures or canned assistant responses in the product path.

## Where is the API reference?

The normative framework vocabulary and semantics live in
[`docs/route-deck-reference.md`](https://github.com/saastoagent/routedeck/blob/main/docs/route-deck-reference.md).
The wiki is a learning layer over that contract.
