# PropertyDesk Reference App Ground Reality And Minimal Spec

Status: superseded planning artifact only
Date: 2026-05-27

This file is retained as historical planning context. The active
product-specific reference-app source of truth is
`docs/medusa-agent-reference-app.md`.

## Purpose

PropertyDesk was a prior product-specific RouteDeck reference-app plan. The
current active plan has moved to the Medusa agent reference app spec. The notes
below remain useful only as historical context for agent boundaries, slice
format, and drift risks.

The reference must not become a SaaS dashboard with a command box. It must also
not make RouteDeck expose or host the agent. The agent runs as an app-owned
LangGraph agent, observes RouteDeck state once RouteDeck exists, and writes by
calling typed RouteDeck product operations.

## Invalidated Prior Attempt

The previous `examples/propertydesk/` implementation was deleted and must not be
used as a reference. It drifted into deterministic intent routing with chat UI
skin and workbench-style framing. In particular:

- a greeting like `hi` did not behave like normal chat
- chat behaved like a capability menu
- the UI emphasized app/workbench structure before agent behavior
- domain action tests passed while the interaction model failed

This failure is part of the spec. Future work must treat it as invalid, not as a
base to rename or polish.

## Current Repo Reality

- RouteDeck currently lives at `agent-lab-powered-projects/routedeck`.
- The reusable framework split exists:
  - `routedeck_core` for product-neutral Python contracts, projections,
    operations, surfaces, runtime state, and validation helpers.
  - `routedeck_langgraph` for optional LangGraph parity checks, transition
    assertions, condition resolver validation, and common graph wiring.
  - `react` for `@routedeck/react` store, hooks, read-only diagnostics
    utilities, and TypeScript contracts.
- The live `examples/` directory is absent or must be treated as empty for
  PropertyDesk planning.
- SaaStoAgent/Corpus is the best current integration reference, but PropertyDesk
  must not copy Corpus product behavior, prompts, route names, or SaaStoAgent
  language.
- The durable Corpus boundary rule remains useful:

```text
RouteDeck exposes.
Product decides.
Runtime validates and commits.
Product UI renders product language.
Diagnostics expose internals read-only.
```

## Terminology Registry

- **Agent**: a conversational app-owned LangGraph agent that can reason over
  context, ask clarifying questions, choose tools/actions, and explain outcomes.
  It is not a keyword router, command parser, or menu.
- **LangGraph agent**: the app agent graph. It has its own app endpoint/stream.
  RouteDeck does not expose it as an operation.
- **Tool**: an agent-callable app function. From Slice 2 onward, write tools
  call `PropertyDeskRouteDeckRuntime.dispatch` instead of mutating product state
  directly.
- **Product operation**: a typed domain operation such as `work_order.triage`,
  `quote.approve`, or `schedule.dispatch`.
- **RouteDeck dispatch**: `PropertyDeskRouteDeckRuntime.dispatch`, the runtime
  write path for typed product operations. It validates, commits, blocks, or
  gates operations.
- **Projection**: RouteDeck's frontend-facing state: surfaces, entities, legal
  operations, blocked operations, current graph position, and presentation data.
- **Surface**: a projected UI area derived from RouteDeck state, such as board,
  work order detail, quote review, approval, outbox, or diagnostics.
- **Quick chip**: a clickable UI control derived from a legal or gated projected
  operation. It is not hardcoded workflow intelligence.
- **Blocked operation**: an operation RouteDeck says cannot run, with a reason.
- **Gated operation**: an operation requiring role, approval, confirmation, or
  missing input before dispatch can succeed.
- **Diagnostics**: read-only explanation of graph position, legal operations,
  blocked/gated operations, guard reasons, and recent dispatch events.
- **Command parser**: message text mapped directly to hardcoded actions. This is
  forbidden as the definition of agent behavior.
- **Product auth/session**: PropertyDesk-owned login/session state. RouteDeck
  does not authenticate users; it consumes the authenticated user/role context
  when computing projection, legal operations, gates, and reasons.

## Target Architecture

```text
LangGraph PropertyDesk agent
  -> observes app state in Slice 1
  -> observes RouteDeck projection/inspect/events from Slice 2 onward
  -> plans a normal agent turn
  -> calls tools
  -> write tools call PropertyDeskRouteDeckRuntime.dispatch once RouteDeck exists

PropertyDesk backend implementing RouteDeckRuntime
  -> product-owned HTTP endpoints backed by PropertyDeskRouteDeckRuntime
  -> RouteDeck-compatible state, projection, dispatch, inspect, stream models
    -> @routedeck/react store, hooks, surfaces, read-only diagnostics
      -> PropertyDesk UI surfaces, chips, forms, approvals
        -> typed product operations for UI controls
```

Graph/runtime state is the source of truth once RouteDeck is introduced.
RouteDeck exposes current truth and legal possibilities. Hard graph guards win
over both the agent and UI.

Exact convergence statement from Slice 2 onward:

```text
All product state writes go through PropertyDeskRouteDeckRuntime.dispatch.
UI control path: UI control -> typed product operation -> dispatch.
Agent path: LangGraph agent selects typed product operation -> tool -> dispatch.
```

Auth/session writes are not RouteDeck dispatches. Login/logout are
PropertyDesk-owned auth operations; the resulting authenticated context is
passed into `PropertyDeskRouteDeckRuntime`.

## Proposed Code Location

```text
agent-lab-powered-projects/routedeck/examples/propertydesk/
```

PropertyDesk should live inside the RouteDeck package because it is a framework
adoption example.

## Spec-Building System

Every implementation slice must use the same compact format:

1. **Purpose**: what the slice proves.
2. **User Experience Contract**: what the user experiences.
3. **Interaction Model**: how the user and system interact.
4. **Capability Contract**: what the system can do.
5. **Architecture Boundary**: allowed and forbidden components.
6. **State And Data**: minimum state required.
7. **Write Path**: exactly how state changes happen.
8. **UI Contract**: what the interface emphasizes and avoids.
9. **Non-Goals**: what must not appear in this slice.
10. **Smoke Checks**: concrete prompts/clicks that must pass.
11. **Drift Signals**: signs the slice has become the wrong thing.
12. **Tests**: automated checks required.
13. **Manual Acceptance**: browser/runtime checks required.
14. **Done Definition**: one paragraph defining completion.

### Anti-Drift Gates

Before implementation, the agent doing the work must answer:

- What is this slice proving?
- What should the user experience?
- What must not appear?
- What is the smallest end-to-end path?
- What would prove this has drifted?

After implementation, the agent must:

- run the slice smoke checks
- open the UI in browser for any frontend slice
- compare the result against drift signals
- report evidence, not just "done"
- stop and update the spec/gate if the implementation shape is wrong

### Development Rules For Agents

- Read this spec before coding.
- Restate the active slice in plain language before editing.
- Implement the smallest vertical slice first.
- Test interaction behavior before domain capability.
- Do not add future-slice concepts early.
- Do not rename wrong architecture into right architecture.
- Do not use a hidden command parser as an agent.
- Do not add RouteDeck before the slice allows it.
- Browser-check UI before claiming done.
- If the plan changes, explain the change and get approval before coding.

### Acceptance Evidence

Every slice closeout must include:

- commands run and results
- tested prompts and/or clicks
- browser URL for UI work
- import/source scan for forbidden dependencies when relevant
- short comparison against drift signals
- known residual risks

### Change Control

If a slice plan changes, document:

- what changed
- why it changed
- which previous assumption was wrong
- what new drift risk was introduced
- whether user approval is required before implementation

### Failure Protocol

When drift is found:

- do not hotfix copy first
- identify whether the plan, gate, or implementation failed
- update the plan/gate before rebuilding
- delete or mark bad examples invalid if they can mislead future work

## Minimal V0 Scope

V0 should stay small. It only needs enough domain behavior to prove the
agent-to-RouteDeck-to-frontend loop.

### Backend

- Slice 1: app-owned LangGraph chat endpoint and in-memory app state only.
- Slice 2 onward: PropertyDesk product endpoints for product-language state,
  actions, agent streaming, and app diagnostics:
  - `GET /api/propertydesk/state`
  - `POST /api/propertydesk/action`
  - `GET /api/propertydesk/stream`
  - `POST /api/propertydesk/inspect`
  - `GET /api/propertydesk/diagnostics/stream`
- Slice 2 onward may also expose a separate generic RouteDeck API plane:
  - `GET /api/routedeck/manifest`
  - `GET /api/routedeck/snapshot`
  - `GET /api/routedeck/projection`
  - `POST /api/routedeck/dispatch`
  - `POST /api/routedeck/inspect`
  - `GET /api/routedeck/stream`
- `POST /api/propertydesk/action` is the product-owned HTTP action endpoint;
  internally it calls `PropertyDeskRouteDeckRuntime.dispatch`.
- Product-owned auth/session endpoints begin in Slice 2:
  - `POST /api/propertydesk/auth/login`
  - `POST /api/propertydesk/auth/logout`
  - `GET /api/propertydesk/auth/session`
  These are not RouteDeck dispatch routes. They establish the user/role context
  consumed by `PropertyDeskRouteDeckRuntime`.
- App-owned agent stream after RouteDeck exists:
  - `POST /api/propertydesk/agent/stream`
- RouteDeck dispatch is for typed product/runtime operations only. Never
  represent agent execution as a RouteDeck operation; do not add
  `agent.objective.run`.
- The shared write contract from Slice 2 onward is:

```text
All product state writes go through PropertyDeskRouteDeckRuntime.dispatch.
PropertyDesk UI control -> typed product operation -> dispatch.
LangGraph agent selected typed product operation -> tool -> dispatch.
```

### Frontend

- Slice 1: simple chat UI only.
- Slice 2 onward: React/Vite app mounted through `RouteDeckProvider`.
- Material Design 3 is the V0 UI principle: clean app shell, restrained color,
  predictable spacing, readable density, clear chips, tabs, lists, dialogs, and
  status treatment.
- Projected surfaces should include board, work order detail, quote review,
  approval, schedule/outbox, timeline, and diagnostics as slices introduce them.
- Enabled quick chips come from `legal_operations` with
  `can_dispatch_now=true`.
- Blocked/gated chip explanations come from inspect output, snapshot guard
  reasons, or blocked-operation reasons.
- Hidden route operations are not product chips.
- Diagnostics are read-only.

### Domain Seed

- Unit `Oak-204`
- Work order `WO-1001`: kitchen leak, priority high
- Vendor quote `Q-17`: requires manager approval before scheduling
- Seeded demo accounts:
  - coordinator: `coordinator@propertydesk.local` / `coordinator-demo`
  - manager: `manager@propertydesk.local` / `manager-demo`
- Authenticated roles:
  - coordinator can triage and request quotes
  - manager can approve quotes
- Blocked operation:
  - scheduling is blocked until quote approval

### Minimal Operations

- `work_order.open`
- `work_order.triage`
- `quote.request`
- `quote.approve`
- `schedule.dispatch`
- Route operations such as `route.open_node`, `route.switch_surface`,
  `route.back`, `route.forward`, and `route.cancel` stay hidden or diagnostic.
  They are never rendered as product quick chips.

## Event Contract

From Slice 2 onward there are three event streams:

1. PropertyDesk RouteDeckRuntime stream:
   - endpoint: `GET /api/propertydesk/stream`
   - event types: `projection_update`, `operation_started`,
     `operation_completed`, `graph_transition`, `guard_failure`,
     `surface_update`, `runtime_status`
   - consumer: `@routedeck/react`

2. PropertyDesk diagnostics stream:
   - endpoint: `GET /api/propertydesk/diagnostics/stream`
   - event types: read-only diagnostics events for graph position, guard
     reasons, operation legality, and dispatch traces
   - consumer: read-only secondary diagnostics surfaces

3. PropertyDesk LangGraph agent stream:
   - endpoint: `POST /api/propertydesk/agent/stream`
   - event types: `agent_observed`, `agent_plan`,
     `agent_selected_operation`, `agent_message_delta`, `agent_done`,
     `agent_error`
   - consumer: PropertyDesk app client

The agent stream may mirror RouteDeck dispatch results into the activity
timeline, but it must not redefine RouteDeck event semantics or represent an
agent run as a RouteDeck operation.

## Minimal File Map

This is the cumulative V0 target structure, not permission for every slice to
create every file. Per-slice architecture boundaries override this map. Slice 1
must not create RouteDeck runtime, manifest, projection, dispatch, surface, or
diagnostics files.

```text
examples/propertydesk/
  README.md
  docker-compose.yml
  backend/
    Dockerfile
    pyproject.toml
    propertydesk/
      __init__.py
      api.py
      agent_graph.py
      domain.py
      manifest.py
      runtime.py
      seed.py
    tests/
  frontend/
    Dockerfile
    package.json
    index.html
    src/
```

## End-To-End Implementation Slices

Each slice must leave a usable running app. A slice is not done if it only adds
backend contracts, frontend chrome, or tests.

### Slice 1: Normal LangGraph Chat Agent

**Purpose**

Prove a normal PropertyDesk LangGraph chat agent before RouteDeck exists.

**User Experience Contract**

The user experiences a simple property-maintenance chat agent.

**Interaction Model**

Free-form chat. The agent handles greetings, understands ordinary maintenance
language, asks clarifying questions when needed, and uses app-owned tools only
when useful.

**Capability Contract**

- greet and converse naturally
- inspect the seeded Oak-204 case
- triage `WO-1001`
- request or discuss quote `Q-17`
- explain why scheduling is blocked until approval

**Architecture Boundary**

Allowed: LangGraph, FastAPI app endpoint, in-memory state, app-owned tools,
simple React chat UI.

Forbidden: RouteDeck imports, RouteDeck routes, RouteDeck dispatch, projection,
surfaces, diagnostics, workbench framing, command parser.

**State And Data**

Oak-204, `WO-1001`, `Q-17`, work-order status, quote approval status, schedule
blocked reason.

**Write Path**

User message -> LangGraph agent -> app-owned tool -> in-memory state.

**UI Contract**

Chat transcript and composer are primary. Suggested prompts are allowed but must
not make the app feel like a command menu. A compact case summary is allowed.

**Non-Goals**

No RouteDeck. No dashboard. No active node/lane/workbench UI. No command-box
demo. No scripted command parser presented as agent behavior.

**Smoke Checks**

- `hi`
- `what can you help with?`
- `there is a leak in Oak-204`
- `what should we do next?`
- `triage it`
- `schedule it`
- unclear input such as `hmm not sure`

**Drift Signals**

- greeting returns a menu or canned capability router response
- exact command phrasing is required
- the UI looks like a workflow debugger or dashboard
- state changes without a plausible agent turn
- any RouteDeck concept appears

**Tests**

- greeting/conversational fallback test
- natural issue report test
- triage tool/state-change test
- schedule-blocked explanation test
- forbidden RouteDeck import/source scan

**Manual Acceptance**

Run backend and frontend. Type the smoke prompts in browser. Confirm the first
visible experience is chat with a property-maintenance agent.

**Done Definition**

Slice 1 is done only when a user can have a basic free-form chat about Oak-204,
the agent can perform the small local maintenance actions, `hi` behaves like
normal chat, and no RouteDeck code or framing exists.

### Slice 2: Seeded Demo Auth And Role Projection

**Purpose**

Introduce RouteDeck with a product-owned seeded auth flow, one authenticated
role-derived projection, projected surfaces, quick chips, and role gates.

**User Experience Contract**

The user signs in as a seeded coordinator or manager account and sees available
actions change based on the authenticated role.

**Interaction Model**

The user assumes a role by logging in with visible demo credentials shown in the
UI. The agent can observe authenticated user/role context and explain
manager-only gates, but it cannot change role, switch accounts, or elevate
privileges by chat. If asked to switch role, it directs the user to log out and
sign in with the appropriate demo account.

**Capability Contract**

- show visible seeded demo credentials
- log in and log out
- persist session across reload
- project authenticated user and role
- show legal and gated role-derived operations
- expose role diagnostics read-only

**Architecture Boundary**

Allowed: product-owned endpoints backed by `PropertyDeskRouteDeckRuntime`,
product-owned auth/session endpoints, `RouteDeckProvider`, one RouteDeck
node/projection, role surfaces, app-owned agent endpoint.

Forbidden: role selector chips, `role.select` dispatch, agent role switching,
agent-as-RouteDeck-operation, product workflow nodes beyond auth/role context,
external identity provider.

**State And Data**

Seeded coordinator and manager demo accounts, session id, authenticated user,
authenticated role, legal operation set, manager-gated operation examples.

**Write Path**

Login/logout are product-owned auth/session writes and do not use RouteDeck
dispatch. RouteDeck state/projection/inspect calls consume the authenticated
session context. Product operation attempts still go through
`PropertyDeskRouteDeckRuntime.dispatch`. There is no role-changing tool or
`role.select` operation in this slice.

**UI Contract**

Material login screen with visible demo credentials, signed-in app shell with
user/role summary, role-derived operation chips, and small read-only
diagnostics. RouteDeck projection determines visible operation chips and gate
reasons.

**Non-Goals**

No property board yet. No quote approval workflow yet. No external auth
provider. No production password/security hardening beyond seeded local demo
accounts.

**Smoke Checks**

- open app and see coordinator/manager demo credentials
- log in as coordinator
- reload and confirm coordinator session persists
- log out
- log in as manager
- inspect gated manager-only action reason
- ask agent why approval is gated
- ask agent to switch role/elevate and confirm it refuses, directing login
- force manager-only backend dispatch as coordinator and confirm rejection

**Drift Signals**

- role chips or role-selector shortcuts replace login
- `role.select` appears as a dispatchable operation
- agent route mutates role/session or silently elevates privileges
- RouteDeck exposes an agent objective operation
- diagnostics become a primary workbench surface instead of read-only secondary
  context
- property board, quote, schedule, or other future-slice code appears

**Tests**

- login success/failure
- logout clears session
- session persists across reload/request
- coordinator and manager projections differ by gate legality
- inspect exposes gate reason from authenticated role context
- forced manager-only backend dispatch as coordinator is rejected
- agent refuses role switch/elevation by chat
- source scan: no property board, quote, schedule, or agent-as-operation leakage

**Manual Acceptance**

Log in and out in browser using both visible demo accounts. Confirm projected
surfaces/chips update by authenticated role. Ask the agent about the gate and
confirm it reads RouteDeck context without changing role.

**Done Definition**

Slice 2 is done when seeded product-owned auth works end to end, RouteDeck
projection/gates are computed from authenticated role context, manager-only
operations are rejected for coordinator at the backend, and the agent remains
app-owned with no privilege-changing tool.

### Slice 3: Property Board And Work Order Open

**Purpose**

Add the first product surface and shared UI/agent dispatch for opening a work
order.

**User Experience Contract**

The user sees a small property board and can open Oak-204's work order by click
or by asking the agent.

**Interaction Model**

The UI displays projected unit/work-order entities. The agent observes the board
projection and chooses `work_order.open` when appropriate.

**Capability Contract**

- project property board
- expose visible units and work orders
- dispatch `work_order.open`
- navigate to selected work order state

**Architecture Boundary**

Allowed: `property_board` node, board surface, entity chips, open operation.

Forbidden: triage, quote review, schedule flow, custom non-RouteDeck navigation
state.

**State And Data**

Oak-204 and `WO-1001` visible on the board.

**Write Path**

Board click -> `PropertyDeskRouteDeckRuntime.dispatch(work_order.open)`.
Agent tool -> `PropertyDeskRouteDeckRuntime.dispatch(work_order.open)`.

**UI Contract**

Projected board surface is primary. Entity chips and legal quick chips derive
from projection.

**Non-Goals**

No state transition beyond opening/selecting the work order.

**Smoke Checks**

- click `WO-1001`
- ask agent to look at Oak-204
- confirm both paths open the same projected work-order context
- force backend dispatch with invalid/missing work-order args and confirm block

**Drift Signals**

- React manually decides navigation outside RouteDeck
- agent bypasses dispatch to set active work order
- board becomes a generic SaaS dashboard
- triage, quote, schedule, or future-slice code appears

**Tests**

- `work_order.open` legality and args
- projection includes visible entity bindings
- UI/agent convergence on dispatch result
- forced backend dispatch/gate test for invalid `work_order.open`
- source scan: no triage, quote, schedule, or future-slice leakage

**Manual Acceptance**

Click and agent paths both open `WO-1001` through RouteDeck and show the same
state.

**Done Definition**

Slice 3 is done when PropertyDesk has a projected board and both user click and
agent action open the same work order through `PropertyDeskRouteDeckRuntime.dispatch`.

### Slice 4: Work Order Detail And Triage

**Purpose**

Add the first meaningful graph-backed product state transition.

**User Experience Contract**

The user sees a work-order detail surface where triage changes state and the
agent can perform the same action.

**Interaction Model**

The user can click a legal triage chip. The agent can observe current state,
decide triage is the next step, and call the same operation.

**Capability Contract**

- project work-order detail, timeline, and actions
- dispatch `work_order.triage`
- update projection after triage
- block repeated triage or remove it from legal operations

**Architecture Boundary**

Allowed: `work_order_detail` node, triage operation, timeline surface.

Forbidden: quote approval, scheduling, hidden frontend workflow rules.

**State And Data**

Work-order status, detail fields, timeline events.

**Write Path**

UI triage chip -> `PropertyDeskRouteDeckRuntime.dispatch`. Agent triage tool ->
`PropertyDeskRouteDeckRuntime.dispatch`.

**UI Contract**

Detail, timeline, and action chips render from projection. Disabled states use
RouteDeck legality/blocked reasons.

**Non-Goals**

No quote gate yet. No schedule completion yet.

**Smoke Checks**

- open `WO-1001`
- triage by click
- reset and triage by agent
- confirm repeated triage is not legal or is blocked with reason
- force backend triage dispatch from the wrong state and confirm block

**Drift Signals**

- UI computes triage legality itself
- agent mutates work-order state directly
- timeline is hardcoded instead of event-derived
- quote, approval, schedule, or future-slice code appears

**Tests**

- triage legality
- triage dispatch state update
- repeated triage blocked/not legal
- projection/timeline changes
- forced backend dispatch/gate test for repeated or wrong-state triage
- source scan: no quote, approval, schedule, or future-slice leakage

**Manual Acceptance**

Run the triage flow by click and by agent. Confirm the same dispatch path and
visible state change.

**Done Definition**

Slice 4 is done when triage is a real RouteDeck operation with visible projected
state/timeline updates and shared UI/agent write behavior.

### Slice 5: Quote Review And Manager Approval Gate

**Purpose**

Prove blocked/gated operations, approvals, and explainability.

**User Experience Contract**

The user sees why quote approval is gated and how signing in as the manager
account makes approval legal.

**Interaction Model**

Coordinator can request/review quote but cannot approve. Manager can approve.
The agent explains the gate from RouteDeck inspect/diagnostics and does not
bypass it.

**Capability Contract**

- project quote review and approval panel
- dispatch `quote.request`
- gate `quote.approve` by manager role
- expose blocked/gated reasons

**Architecture Boundary**

Allowed: quote node/surfaces, approval panel, manager role gate.

Forbidden: agent self-approval as coordinator, agent account switching,
hardcoded UI approval logic.

**State And Data**

Quote `Q-17`, approval status, authenticated role, gate reason.

**Write Path**

UI approval chip/form -> `PropertyDeskRouteDeckRuntime.dispatch`. Agent
quote/approval tool -> `PropertyDeskRouteDeckRuntime.dispatch`.

**UI Contract**

Quote review and approval panel show legal, gated, and blocked operations from
projection/inspect.

**Non-Goals**

No scheduling dispatch yet except showing why it is blocked.

**Smoke Checks**

- request quote as coordinator
- see approval blocked/gated as coordinator
- ask agent why approval is blocked
- switch to manager
- approve quote
- force backend approval dispatch as coordinator and confirm gate

**Drift Signals**

- manager gate lives only in React
- agent can approve while coordinator
- blocked reason is copy-only and not from RouteDeck
- approval is hidden instead of explainable
- schedule dispatch or outbox completion code appears

**Tests**

- coordinator cannot approve
- manager can approve
- blocked/gated reason appears in inspect/projection
- agent does not select blocked approval
- forced backend dispatch/gate test for coordinator approval
- source scan: no schedule dispatch, outbox completion, or future-slice leakage

**Manual Acceptance**

Run the coordinator-to-manager quote approval flow and confirm UI and agent see
the same gate.

**Done Definition**

Slice 5 is done when approval gating is enforced by RouteDeck, visible in the UI,
and respected by the agent.

### Slice 6: Schedule, Outbox, And Completion Loop

**Purpose**

Close the PropertyDesk maintenance scenario end to end.

**User Experience Contract**

The user sees the leak workflow progress from observation to scheduled/outbox
state, with the agent acting only through legal operations.

**Interaction Model**

The agent can work through the objective, stop at approval when gated, continue
after manager approval, and schedule only when legal. The user can intervene by
clicking the same projected operations.

**Capability Contract**

- project schedule and outbox surfaces
- block `schedule.dispatch` until quote approval
- dispatch schedule after approval
- emit timeline/outbox events

**Architecture Boundary**

Allowed: schedule/outbox surfaces, full scenario flow, RouteDeck diagnostics.

Forbidden: bypassing approval, hidden background completion, non-RouteDeck write
path.

**State And Data**

Approved quote, schedule state, outbox events, timeline events.

**Write Path**

UI schedule chip -> `PropertyDeskRouteDeckRuntime.dispatch`. Agent schedule
tool -> `PropertyDeskRouteDeckRuntime.dispatch`.

**UI Contract**

Schedule/outbox surfaces show blocked-before/legal-after status and timeline.

**Non-Goals**

No broad portfolio management. No database. No vendor marketplace.

**Smoke Checks**

- attempt schedule before approval and see blocked reason
- approve quote
- schedule by click
- reset and complete by agent with approval intervention
- force backend schedule dispatch before approval and confirm block

**Drift Signals**

- schedule succeeds before approval
- agent completes hidden steps without visible dispatch/events
- outbox is static copy
- user intervention path diverges from agent path
- database, portfolio, marketplace, or unrelated future scope appears

**Tests**

- schedule blocked before approval
- schedule legal after approval
- full agent path reaches scheduled/outbox state
- timeline/outbox events emitted
- forced backend dispatch/gate test for schedule before approval
- source scan: no database, portfolio, marketplace, or unrelated future scope

**Manual Acceptance**

Complete the Oak-204 leak flow in browser and confirm every write appears as a
RouteDeck dispatch/event.

**Done Definition**

Slice 6 is done when the full small maintenance scenario runs end to end and
approval/scheduling legality is enforced through RouteDeck.

### Slice 7: Diagnostics, Docker, And Reference Polish

**Purpose**

Make the example credible as a reference app instead of a local prototype.

**User Experience Contract**

A new developer can run the example and understand the agent/RouteDeck/frontend
contract from the app and README.

**Interaction Model**

The app remains agent-led, but diagnostics are available read-only for learning
and debugging.

**Capability Contract**

- stable seeded reset
- documented runtime routes
- complete scenario smoke path
- Docker Compose run path
- readable read-only secondary diagnostics

**Architecture Boundary**

Allowed: polish, docs, Docker, read-only secondary diagnostics, browser smoke
tests.

Forbidden: new product scope, Corpus names, marketing page, copy-only
architecture claims.

**State And Data**

Same minimal seed, with reset behavior for repeatable demos.

**Write Path**

No new write path. All writes remain `PropertyDeskRouteDeckRuntime.dispatch`.

**UI Contract**

Material layout is clean, responsive, and dense enough for a tool. Diagnostics
do not dominate the primary user flow.

**Non-Goals**

No public package release work unless separately scoped. No broad SaaS features.

**Smoke Checks**

- run backend tests
- run frontend build/type-check
- run Docker Compose
- browser-smoke the complete scenario
- read diagnostics while running the scenario
- scan for public `/api/routedeck/*`, Corpus names, and agent-as-operation

**Drift Signals**

- docs claim behavior not visible in app
- Docker path differs from local runtime behavior
- diagnostics become the primary UI or a workbench/debugger surface
- polished UI hides gates or dispatch evidence
- public `/api/routedeck/*`, Corpus names, or agent-as-operation appears

**Tests**

- backend suite
- frontend type-check/build
- Docker smoke
- browser smoke for complete scenario
- source scan: no PropertyDesk-specific behavior under `/api/routedeck/*`, no
  Corpus names, and no agent-as-operation leakage

**Manual Acceptance**

Fresh run from README commands. Complete the scenario in browser and compare the
visible app to the architecture contract.

**Done Definition**

Slice 7 is done when a new user can run PropertyDesk locally, see the full
agent-to-RouteDeck-to-frontend loop, and verify it with documented tests and
smoke evidence.

## Cross-Slice Re-Evaluation

Subagent-style review identified these remaining misinterpretation risks:

- **Agent risk**: future work may again implement deterministic keyword routing
  and call it an agent. Mitigation: Slice 1 smoke starts with `hi`, unclear
  input, and natural maintenance language before domain actions.
- **RouteDeck risk**: future work may expose the agent as a RouteDeck operation.
  Mitigation: terminology and architecture boundary say the agent is app-owned;
  RouteDeck dispatch is only for typed product operations.
- **Frontend risk**: future work may hardcode workflow intelligence in React.
  Mitigation: slice contracts require surfaces, chips, disabled states, and
  reasons to derive from projection/inspect once RouteDeck exists.
- **Diagnostics risk**: future work may turn diagnostics into a primary
  workbench/debugger surface. Mitigation: diagnostics are read-only and
  secondary; each slice defines a user experience contract before diagnostics.
- **Scope risk**: future work may add SaaS/portfolio features too early.
  Mitigation: each slice has non-goals and a minimal state/data section.
- **Proof risk**: future work may pass backend tests while failing the browser
  experience. Mitigation: every UI slice requires manual browser acceptance and
  acceptance evidence.

## Explicit Non-Goals For V0

- No broad SaaS dashboard.
- No generic natural-language command parser.
- No database.
- No external identity provider or production auth hardening.
- No multi-property portfolio management.
- No tenant billing, documents, or vendor marketplace.
- No copying Corpus/SaaStoAgent names, routes, prompts, or domain semantics.
- No presenting local scripted commands as proof of agentic operation.
- No replacing the agent path with a deterministic command parser.
- No exposing the LangGraph agent itself as a RouteDeck operation.
- No PropertyDesk-specific behavior under `/api/routedeck/*`. Product behavior
  uses `/api/propertydesk/*`; generic RouteDeck state/projection/dispatch/inspect
  may use `/api/routedeck/*`.

## Design Constraint

Every visible feature from Slice 2 onward must reinforce this contract:

```text
Agent observes RouteDeck projection.
Agent plans against legal RouteDeck operations and projected surfaces.
Agent executes by calling tools that dispatch typed product operations.
PropertyDeskRouteDeckRuntime.dispatch validates and commits or blocks.
Frontend surfaces, chips, approvals, and disabled states change because
RouteDeck projection changes.
Diagnostics explain the state, gate, and decision.
```
