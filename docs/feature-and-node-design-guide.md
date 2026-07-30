# RouteDeck Feature And Node Design Guide

Status: current design guidance

This guide helps product teams decide how to divide a feature into RouteDeck
nodes and how the surrounding operations, providers, guards, surfaces, and
agent policies work together.

It is design guidance, not a replacement for the normative
[RouteDeck reference](./route-deck-reference.md).

## The Mental Model

Think of a RouteDeck application as a building:

- A **Feature** is a department that owns part of the product.
- A **Node** is a room in that department.
- An **Operation** is an action available in that room.
- A **Provider** fetches the authoritative facts needed for an action.
- A **Guard** deterministically decides whether the action may proceed.
- A **Handler** performs the product action.
- An **Outcome** reports what actually happened.
- A **Transition** maps that outcome to the next room.
- A **Surface** is the control panel shown to the user.
- An **AgentPolicy** gives the product agent trusted guidance.

RouteDeck owns the rooms, legal actions, supervision, and movement between
rooms. The consuming product owns the meaning, business logic, prompt, model,
UI, data, and external effects.

## Start With The Feature Boundary

A feature should own one coherent product responsibility. It should contain
complete nodes and their declarations rather than fragments of nodes owned by
several features.

Ask:

> Which product responsibility owns these locations, operations, surfaces, and
> implementations?

The answer should be a product boundary such as Catalog, Checkout, Sources, or
Evaluation, not a generic technical layer.

## Decide Whether You Need A Node

Create a new node when at least one of these changes:

- the durable product location;
- the set of legal operations;
- the route, deep-link, back, forward, or cancellation behavior;
- the authoritative context or entity scope;
- the interaction requires a distinct history entry.

Do not create a node merely because a component is loading, empty, successful,
expanded, or showing an error. Those are usually surface or status variations
inside the same node.

The useful test is:

> What can legally happen here, and what authoritative outcome moves the user
> somewhere else?

If that answer does not change, another node is probably unnecessary.

## Design Operations And Transitions Together

An operation is the only path for an application-semantic read or write. Agent
tool calls and surface affordances must invoke the same supervised operation;
neither may modify canonical state directly.

Every operation declares typed inputs and named outcomes. At the current node,
each operation/outcome pair maps to exactly one target node.

```text
user or surface requests an operation
  -> RouteDeck validates the request and current node
  -> providers load authoritative facts
  -> guards evaluate those facts
  -> review is staged when required
  -> the product handler executes
  -> the handler reports a declared outcome
  -> RouteDeck commits state and follows the matching transition
```

Prefer meaningful outcomes such as:

```text
created
already_exists
needs_input
rejected
failed
```

The handler reports an outcome. It does not navigate by itself.

## Providers, Guards, Handlers, And Review

These responsibilities must remain separate.

### Provider

A provider loads current product facts or an allowed entity set. Examples
include the current cart, signed-in owner, ready source revision, or available
shipping options.

The model's memory and browser state are not authoritative product facts.

### Guard

A guard is deterministic product code. It decides whether an operation may
continue from the provider facts and current request.

```text
Start checkout requested
  -> provider loads the real cart
  -> guard checks that the cart exists and is not empty
  -> pass: checkout handler may run
  -> fail: handler never runs
```

A policy cannot grant permission and a prompt cannot bypass a guard.

### Handler

The handler performs the product-owned action only after RouteDeck has accepted
the request, resolved its context, and passed its guards and review boundary.
It returns a declared result or fails visibly.

### Review

A guard answers, "May this operation proceed?"

Review answers, "This operation is permitted, but must a person approve it
before execution?"

Use review for consequential actions such as deployment, deletion, payment, or
another external write that needs explicit confirmation.

## Agent Prompt And Policy Scopes

Keep one stable product prompt for the agent's identity, voice, and universal
rules. Use `AgentPolicy` for guidance that applies only in a particular RouteDeck
scope.

RouteDeck can resolve policies from:

- **Framework** - always-active RouteDeck execution and state rules;
- **Feature** - active anywhere inside that product feature;
- **Node** - active at one product location;
- **Capability** - active with a capability declared at that node;
- **Surface** - active while that surface is active;
- **Operation** - active while that operation is currently legal.

On every model call, RouteDeck reloads the current session, resolves the active
node and relevant policies, builds safe model context, and exposes only legal
tools.

```text
stable product prompt
  + currently relevant trusted policies
  + current public state and legal tools
  -> product agent
```

When the node changes, the applicable policies and tools change on the next
model call.

Policies guide model behavior. They do not enforce application permissions.
Operations, providers, guards, review, input validation, and opaque-handle
resolution enforce the boundary in code.

## How Much Navigation Should The Agent Know?

The agent normally needs its current location and legal ways forward, not a
copy of the entire Navgraph.

Navigation should be expressed through declared operations and transitions.
Give navigation operations clear titles and descriptions, and use suggested
actions when an important next step should be prominent.

Broad product knowledge such as which major features exist can live in the
stable product prompt or another product-owned, read-only knowledge source.
Knowing that a destination exists does not make navigation to it legal.

## Surfaces And Suggested Actions

A surface receives projected public props and presents product UI. Its
state-changing affordances dispatch declared operations through RouteDeck.

A suggested action is a compact invitation to perform an operation. It can help
the model or UI present a useful next step, but it does not create authority or
a separate execution path.

Avoid these shortcuts:

- letting a surface mutate canonical state directly;
- treating every legal operation as a button;
- using suggested actions as a substitute for navigation design;
- copying business logic into the frontend.

## Public And Private State

Only safe public values should enter browser projection or model context.

Keep credentials, private form values, internal database identifiers, and
private bindings on the server. When the browser or model must refer to an
entity, use an opaque handle whose current node, operation, entity kind,
allowlist, session, and version are checked before resolution.

## Failure And Recovery

Design failures before implementation, especially for external writes.

An external request may be:

- definitely not sent;
- possibly sent, with the outcome unknown;
- sent and answered.

An outcome-unknown write must enter explicit recovery. RouteDeck must not
silently retry it or claim success. Recovery may require refreshing trusted
facts, reconciling with the external system, or asking the user to choose an
explicit next action.

## Medusa Example

The Medusa reference application uses:

- one permanent buyer-assistant prompt;
- a Checkout feature with four nodes;
- feature-owned operations, providers, guards, surfaces, and transitions;
- one Checkout-scoped `AgentPolicy` that prevents collecting protected contact
  and address values in chat;
- deterministic checkout guards that decide whether product operations may
  execute.

The policy tells the agent to direct private input to the protected form. The
guards and private-form boundary enforce what the application may actually do.

Medusa demonstrates correct policy wiring, but it does not provide a distinct
product policy for every node.

## Recommended Design Order

For one feature:

1. State the feature's product responsibility.
2. Identify only the durable locations that need nodes.
3. List the operations legal at each node.
4. Define typed inputs and meaningful outcomes for every operation.
5. Identify the authoritative facts each operation requires.
6. Add providers for those facts and deterministic guards for permission.
7. Add review where permission alone is insufficient.
8. Map every operation outcome to exactly one target node.
9. Design surfaces and bind their affordances to operations.
10. Add suggested actions only where they clarify the next step.
11. Add feature, node, surface, capability, or operation policies where the
    agent needs scoped guidance.
12. Define public/private state and explicit recovery behavior.

## Final Review Checklist

- Does every node represent a meaningful durable location?
- Is every operation legal only where it should be?
- Do UI and agent actions use the same operation runner?
- Do providers load current authoritative facts?
- Are permission decisions enforced by deterministic guards?
- Are consequential operations protected by review where needed?
- Does every outcome have one exact transition target?
- Are surfaces presentation and dispatch only?
- Are policies guidance rather than security enforcement?
- Does the agent receive only current legal tools?
- Are private identifiers and values kept out of public/model context?
- Are uncertain external writes handled without blind retries?
- Can the complete feature be compiled and bound without missing or extra
  handlers, providers, or guards?

