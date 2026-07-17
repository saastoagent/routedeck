# RouteDeck Runtime-Boundary Refactor Planning Handoff

You are taking over architecture planning for the standalone RouteDeck repository.

Your task is to inspect the current source and create a focused implementation
plan for the approved runtime-boundary refactor described below. Do **not**
implement the refactor yet. Stop after writing and self-reviewing the plan so the
user can approve it.

## Workspace And Starting State

- Authoritative repository: `D:\Dev\AI Projects\routedeck`
- Do not use the former nested checkout under `agent-core`.
- Runtime location: local Windows only. Do not use or probe the Mac mini or any
  remote host.
- Branch at handoff: `main`
- HEAD at handoff: `49a6509 docs: correct extracted Medusa compose command`
- The worktree was clean when this handoff was written.
- Do not perform Git operations unless the user explicitly requests them.
- There is no repository `AGENTS.md`; follow `instructions.md` and the authority
  chain below.

The repository contains private migrated context under
`codex_chats_and_memories/`. Use it to recover rationale, but treat current
source and active authority documents as stronger evidence than old rollout
summaries. In particular, older memories describing product-owned chat or the
old SQLite adapter are historical.

## Mandatory Reading Order

Read these before proposing the plan:

1. `instructions.md`
2. `critical_prompt.md`
3. `context.md`
4. `decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md`
5. `decisions/ADR-005-operation-centric-state-and-consumer-structure.md`
6. `docs/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md`
7. `docs/superpowers/plans/2026-07-14-routedeck-architecture-cleanup.md`
8. `docs/route-deck-reference.md`
9. `docs/medusa-agent-reference-app.md`
10. `architecture/code-map.md`
11. `architecture/components/core-runtime-contract.md`
12. `architecture/components/langgraph-adapter.md`
13. `architecture/components/react-runtime-debugger.md`
14. `test_index/README.md`
15. `codex_chats_and_memories/README.LOCAL.md`
16. `codex_chats_and_memories/memory/MEMORY.project-extract.md`, especially the
    RouteDeck/Medusa task group
17. `codex_chats_and_memories/rollout_summaries/2026-07-11T04-32-20-aLJN-standalone_routedeck_medusa_buyer_agent_boundary_design.md`

The controlling direction is ADR-004 -> ADR-005 -> approved design -> current
source -> the new plan you will write. ADR-003 is historical rationale only.
The July 11 implementation plan is completed slice history. Do not resume the
retired July 10 full-stack refactor plan.

## Planning Objective

Create a dated implementation plan under `docs/superpowers/plans/` for a clean
architectural refactor that:

1. moves reusable runtime assembly and LangGraph conversation driving out of
   the Medusa consumer and into RouteDeck;
2. removes the Medusa-specific conversation-entry transport in favor of a
   RouteDeck-owned assistant-initiated turn;
3. replaces reducer-shaped React conversation presentation transitions with
   named actions;
4. splits the six confirmed oversized responsibility hotspots into cohesive
   modules without changing public behavior;
5. strengthens executable boundary checks so they cannot bless the current
   misplaced runtime assembly again; and
6. preserves the complete buyer-visible chat, surface, hybrid, navigation,
   checkout, review, and confirmation behavior.

The plan must be implementation-ready: exact files to create, modify, move, and
delete; interface shapes; dependency direction; ordering; focused validation;
documentation updates; and explicit clean-break deletions.

## Locked Product And Framework Boundary

### RouteDeck owns

- immutable application and feature compilation;
- the canonical session aggregate and named state actions;
- navgraph validation, navigation, history, deep links, and resume handles;
- context lenses, framework policies, legal-operation exposure, private entity
  bindings, and scoped public handles;
- supervision, leases, reviews, operation execution coordination, recovery,
  effects, public projections, and event state;
- generic runtime assembly for runner, navigation, store lifecycle, projector,
  ID generation, and adapter-facing runtime services;
- ordinary conversation lifecycle, assistant-initiated and user-initiated
  turns, durable history, replay, interruption, interaction handshake, and SSE;
- generic LangGraph event-to-RouteDeck translation;
- SQLAlchemy persistence for explicit SQLite and PostgreSQL URLs;
- generic FastAPI dependency derivation and product-neutral routes;
- headless frontend state, synchronization, surfaces, conversation primitives,
  and React integration.

### Medusa owns

- Store API configuration, authentication, typed client protocol, HTTP resource
  adapters, wire decoding, and commerce evidence;
- catalog, cart, checkout, payment, order, and reconciliation business logic;
- feature declarations, typed bindings, product providers, product guards, and
  product session initialization such as creating the real cart;
- buyer-market facts: region, country, currency, sales channel, and configured
  payment provider;
- prompts, model selection, agent personality, turn policy, LangGraph graph
  definitions, and structured graph selection;
- product surface components, affordances, copy, styling, health, and Medusa
  readiness.

Medusa may have a very small composition root that passes product declarations,
callbacks, and configured adapters to RouteDeck. It must not construct or
reimplement generic RouteDeck runtime algorithms.

## Boundary Audit To Incorporate

### `examples/medusa-agent/backend/medusa_agent/agent_driver.py`

This is a real boundary violation. Almost all of the file is generic:

- consuming LangGraph `astream_events`;
- validating stream envelopes and model run identities;
- enforcing serial tool-call behavior;
- emitting assistant delta/reset events;
- extracting review requirements;
- selecting and validating the final assistant response;
- proving that the final response was streamed;
- converting LangChain messages into durable RouteDeck conversation turns;
- closing interrupted streams.

Move that behavior into `routedeck_langgraph`, near its existing conversation,
middleware, model-context, and tool-wrapper modules. The reusable driver should
depend on narrow RouteDeck ports and a narrow ID factory, never on a concrete
`RouteDeckOperationRunner`.

Medusa should retain only its graph definitions and structured selection of the
entry graph versus the normal buyer graph. Product event tags that the generic
driver should ignore must be supplied explicitly as typed configuration, not
embedded Medusa imports or phrase heuristics.

### `examples/medusa-agent/backend/medusa_agent/runtime_factory.py`

This file contains substantial reusable framework assembly:

- `MedusaRuntime` duplicates a generic runtime container;
- it constructs `RouteDeckOperationRunner`;
- it constructs `RouteDeckNavigationRunner`;
- it owns generic load/close lifecycle behavior;
- it opens the SQLAlchemy store and codec;
- it selects generic runtime defaults and passes the same runner across
  transports.

The current design permits a product composition root to wire adapters, but the
stronger open-source framework goal is that products should not repeat this
assembly. Introduce a product-neutral RouteDeck runtime boundary in the
framework. It should own the compiled/bound app, runner, navigation, store,
clock, notifier, ID factory, projection service, lifecycle, and adapter-facing
services.

The SQLAlchemy package may provide the persistent runtime/store opening helper,
and the FastAPI package may derive its dependency object from the generic
runtime. Keep dependency direction one-way: optional adapters depend on core;
core never imports FastAPI, SQLAlchemy, LangGraph, React, or Medusa.

The `MedusaRuntime` class should disappear. Medusa should pass a bound product
application plus product-specific callbacks to a generic RouteDeck builder.

The following must remain product-owned even after the factory is removed:

- `bind_medusa_app(...)`;
- catalog public-route-key validation;
- buyer session/private-market creation;
- the one-time, journaled real-cart initialization operation;
- product handlers, providers, guards, and configured Medusa client.

### `examples/medusa-agent/backend/medusa_agent/runtime.py`

This file is mixed.

Keep in Medusa:

- reading product settings;
- creating the typed Medusa Store client and optional Medusa evidence recorder;
- resolving and validating region, country, currency, and sales channel;
- checking the real Medusa dependency;
- selecting configured product agent graphs/models without fallback;
- payment-provider configuration;
- the small product application container and Medusa readiness result.

Move into RouteDeck:

- clock and notifier defaults;
- codec/store/runtime assembly;
- default runtime ID generation;
- generic store/lease readiness;
- `RouteDeckDependencies` construction;
- generic runtime close/lifecycle behavior.

The scripted test model is permitted only in explicit test infrastructure. The
live product runtime should not dynamically discover test behavior. Plan an
explicit injection seam from the test bootstrap instead.

### `examples/medusa-agent/backend/medusa_agent/session.py`

This file is mostly correctly product-owned.

Keep:

- `BuyerMarket`;
- conversion of buyer-market facts into classified RouteDeck private state;
- the Medusa buyer-session factory.

Move/remove:

- replace `MedusaSessionProjector` with a reusable RouteDeck configured
  projector accepting an injected clock and product public-key-validator
  factory;
- remove `project_medusa_session`, which duplicates framework projection and is
  primarily a test convenience;
- avoid recompiling the Medusa application inside every session helper; inject
  the already compiled/bound application through the generic runtime/session
  factory boundary.

### `examples/medusa-agent/backend/main.py`

This related composition file currently constructs the Medusa LangGraph driver,
manually exposes generic dependency providers, and mounts a separate product
entry router. After the refactor it should only:

- obtain the configured product application;
- mount the generic RouteDeck router/runtime;
- configure explicit browser-origin policy;
- mount product health/readiness;
- own FastAPI lifespan at the product-host level while delegating generic
  runtime close behavior.

It must not construct a concrete operation runner, navigation runner, generic
conversation driver, or product-specific conversation-entry transport.

### `scripts/check_boundaries.py`

The current `shared_runner` check encodes the misplaced architecture. It expects
the runner, `MedusaRuntime`, navigation runner, and `RouteDeckDependencies` to be
constructed inside Medusa. This explains why the existing 8/8 boundary report
can pass while generic runtime assembly still lives in the product.

Rewrite this check so it proves at least:

- Medusa production code does not construct `RouteDeckOperationRunner`;
- Medusa production code does not construct `RouteDeckNavigationRunner`;
- Medusa production code does not construct generic `RouteDeckDependencies`;
- Medusa does not implement LangGraph event-to-RouteDeck stream translation;
- one generic RouteDeck runtime supplies the same runner to operations,
  navigation, chat, surfaces, and FastAPI;
- product code supplies declarations, bindings, callbacks, agent graphs, and
  commerce adapters only;
- RouteDeck core still has no reverse imports into optional adapters or Medusa.

Keep this as one focused executable boundary proof. Do not respond by creating
dozens of narrow unit tests.

## Generic Conversation Entry

Remove the product-specific entry path cleanly:

- `examples/medusa-agent/backend/medusa_agent/api/entry.py`
- `examples/medusa-agent/backend/medusa_agent/entry_conversation.py`
- `examples/medusa-agent/frontend/src/app/conversationEntryClient.ts`

Do not retain compatibility endpoints, lazy aliases, deprecated exports, or
fallbacks.

Add a RouteDeck-owned assistant-initiated conversation request alongside the
existing user-initiated chat request. The agent-driver contract should receive
a typed trigger such as assistant entry versus user message. It must not use an
empty-string convention, regex, phrase matching, or inferred intent.

Both trigger types must use the same RouteDeck lifecycle:

- execution lease and fencing;
- durable mutation identity and replay;
- conversation persistence;
- assistant deltas/resets/finalization;
- interruption and outcome-unknown handling;
- session-version and projection-version synchronization;
- the authoritative interaction handshake that makes projected surfaces inert
  while an agent turn is active.

The initial welcome text must continue to come from the Medusa system prompt.
No welcome sentence or phrase router may be hardcoded in RouteDeck or Medusa
transport code.

## React Conversation Presentation

Replace the reducer-shaped implementation in
`packages/react/src/conversation/transitions.ts` with a conversation
presentation model/coordinator exposing intention-revealing named actions, for
example:

- start stream;
- apply conversation snapshot;
- append user message;
- append assistant delta;
- reset streamed assistant text;
- finalize assistant message;
- require review;
- record failure;
- finish stream;
- remove a retained request's provisional messages.

Transport-event decoding can remain a typed mapping from declared event type to
the corresponding named action. Do not use a generic reducer API, arbitrary
action objects, or a second canonical state authority. The model is ephemeral
React presentation state; `RouteDeckObservableState` remains the canonical
frontend mirror of RouteDeck runtime state.

## Oversized Responsibility Hotspots

Plan a cohesive split for all six confirmed hotspots. The goal is real module
ownership, not line-count theater or pass-through wrappers.

Current sizes at handoff:

| File | Lines | Required split |
| --- | ---: | --- |
| `routedeck_core/app/compiler.py` | 867 | compilation orchestration, declaration/reference validation, route-entry compilation, frontend-contract generation, executable path derivation |
| `routedeck_fastapi/router.py` | 536 | router composition, session/contract endpoints, dispatch/navigation/review endpoints, event endpoints, private-form endpoints, inspection endpoints |
| `routedeck_sqlalchemy/store.py` | 699 | store lifecycle, session operations, turn operations, operation/review commits, private state, events/retention/maintenance |
| `packages/core/src/contracts/decode.ts` | 1125 | shared decoding primitives, projection decoding, event/result decoding, compiled-contract decoding, private-form/inspection decoding |
| `packages/core/src/store/store.ts` | 564 | store facade, bootstrap/recovery, synchronization, operation/review coordination, navigation/history composition |
| `examples/medusa-agent/backend/medusa_agent/medusa/client/http.py` | 551 | catalog/region resources, cart resources, checkout/payment resources, order resources, common typed transport |

Rules for these splits:

- preserve one obvious canonical public API per subsystem;
- internal barrels/facades are acceptable only as canonical module surfaces,
  not compatibility shims;
- use composition or focused service objects where it clarifies lifecycle;
- do not introduce multiple inheritance merely to hide line count unless the
  plan proves the mixin boundaries are independently coherent;
- keep Medusa Store endpoint templates inside the typed Medusa client package,
  even when split across resource modules;
- update the boundary inventory to allow the explicit resource-module set, not
  arbitrary HTTP calls elsewhere;
- no raw persistence SQL; keep SQLAlchemy ORM support for SQLite and PostgreSQL;
- do not split the broad checkout declaration/provider/model files in this
  phase. The user explicitly deprioritized that concern.

## Locked Clean-Break Rules

- No legacy namespace, lazy root access, deprecated alias, compatibility export,
  duplicate endpoint, alternate event name, or old constructor path.
- Delete superseded source and tests after callers are migrated.
- No hidden fallback execution paths.
- No fixtures, canned responses, synthetic products, or deterministic model
  behavior in product runtime paths.
- No phrase routing, keyword maps, regex intent classification, or hardcoded
  conversational responses.
- Missing dependencies and invalid invariants fail loudly.
- RouteDeck does not invoke commerce tools directly; the injected host executor
  remains the product side-effect boundary.
- The LangGraph execution graph remains separate from the RouteDeck navgraph.
- The browser never calls Medusa `/store/*` directly.
- The model and browser receive scoped opaque handles; private Medusa IDs remain
  in classified bindings.

## User-Visible Invariants

The plan must explicitly preserve and verify:

- the app opens on the home/lounge node with a model-authored welcome;
- a simple `hello` does not force navigation to products;
- Enter sends chat by default;
- a thinking indicator appears immediately after a user message;
- assistant text arrives incrementally over SSE rather than all at once;
- quick actions stay near the composer and remain distinct from product
  surfaces;
- product surfaces are dynamic, interactive RouteDeck-controlled UI embedded in
  the conversation/workbench stream;
- surfaces become inert immediately while an agent turn owns the session;
- chat-driven, surface-driven, and hybrid operations converge on the same
  supervised runner and durable session authority;
- the Navgraph remains a collapsible, scrollable, read-only full sitemap;
- deep links, browser back/forward, private forms, review, mock `pp_system`
  payment, placement, reconciliation, and confirmation preserve current
  behavior;
- real Medusa remains the commerce source of truth.

## Planning And Verification Style

The user does not want another test-heavy detour. The plan should be organized
as focused architectural vertical slices. Each slice must leave a usable product
path intact and end with the smallest meaningful proof.

Recommended slice order:

1. Introduce the generic RouteDeck runtime container/builder and migrate Medusa
   assembly to it.
2. Move the generic LangGraph conversation driver into RouteDeck and narrow its
   dependencies.
3. Add the typed assistant-entry trigger and delete the Medusa entry transport.
4. Replace reducer-shaped React presentation transitions with named actions.
5. Split the six large files by responsibility, one subsystem at a time.
6. Rewrite executable boundary checks and remove obsolete architecture
   assumptions.
7. Update authority/reference/code-map documentation.
8. Run focused backend/frontend/boundary checks, then one real UI chat story,
   one surface story, and one hybrid story. Run the complete buyer flow only as
   the final product gate.

The plan must name exact existing tests to update or run after inspecting
`test_index/README.md` and current test call sites. Prefer focused contract,
integration, typecheck, build, and browser-story commands. Do not introduce a
global coverage target or treat test count as progress.

## Required Plan Deliverable

Create exactly one new dated plan in `docs/superpowers/plans/`, with a clear
name such as `2026-07-15-routedeck-runtime-boundary-refactor.md`.

The plan must contain:

1. current-state evidence and the boundary verdict;
2. proposed final package/file layout;
3. public interfaces and ownership for the generic runtime, LangGraph driver,
   assistant-entry trigger, configured projector, and React presentation model;
4. exact file-by-file create/modify/delete lists for every slice;
5. call-site migration order with no compatibility period;
6. failure, replay, concurrency, and cleanup semantics;
7. focused validation commands and the product behavior each command proves;
8. documentation and boundary-check updates;
9. explicit non-goals, including no checkout-module split and no UI redesign;
10. final chat, surface, hybrid, and full buyer-flow acceptance gates.

Decide during planning whether this ownership move warrants a new ADR or a
focused amendment to ADR-005. State the recommendation and include the exact
documentation action in the plan.

Self-review the plan for stale paths, placeholders, compatibility shims,
ownership contradictions, missing deletions, test overreach, and any path that
would leave generic runtime logic inside Medusa.

Then stop and present the plan to the user for approval. Do not implement,
stage, commit, push, start the stack, or mutate databases in the planning turn.
