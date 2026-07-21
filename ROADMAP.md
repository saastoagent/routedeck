# RouteDeck Roadmap

Status: public product direction

This roadmap describes intended outcomes. It is not implementation authority
and does not make unreleased behavior part of RouteDeck's contract. Current
source, accepted ADRs, the [RouteDeck reference](./docs/route-deck-reference.md),
and the [feature coverage matrix](./architecture/feature-coverage.md) control
implemented behavior.

## Vision

RouteDeck is the application-state and interaction-governance runtime for
agentic applications. Products keep ordinary feature modules, API clients,
business rules, prompts, models, graph topology, and UI. RouteDeck compiles one
interaction contract, gives agents only current legal context, supervises the
same semantic operations for agents and UI, and keeps durable server and
browser state coherent.

The intended developer experience is:

```text
declare the application
  -> compile its interaction contract
  -> govern every agent and UI operation
  -> explain exactly what happened
```

The Medusa buyer application is the first acceptance proof. Its product code
should remain ordinary application code; it is not the source of future
RouteDeck scope.

## Product Principles

- The product remains the authority for domain facts and side effects.
- RouteDeck remains the authority for interaction state and supervision.
- Agent prose is never an application state change.
- Agent tools and UI affordances use one declared operation path.
- Missing dependencies and uncertain effects remain visible failures.
- Private identifiers and values remain outside public and model context.
- Examples prove framework behavior; they do not drive unrelated product
  expansion.
- New adapters and protocols are demand-led and optional, not core roadmap
  commitments.

## M0: Open-Source Alpha

Objective: publish the current implemented capability as an honest,
installable, reproducible public alpha.

Outcomes:

- clean Python and npm artifacts installed and tested from their archives;
- current release contracts and a sanitized local proof bundle;
- public project governance, security, contribution, support, and release
  guidance;
- non-destructive CI using the locked development toolchain;
- a concise external-user README and explicit alpha limitations;
- trusted publishing and registry publication only after separate approval.

M0 does not add runtime, Medusa, authentication, protocol, or observability
features.

## M1: Agent-Native Authoring

Objective: make RouteDeck unusually easy for developers and coding agents to
adopt correctly.

Outcomes:

- machine-readable documentation and maintained authoring skills;
- structured compiler diagnostics with concrete remediation;
- focused project, feature, and contract validation commands;
- small copyable authoring examples and generated contracts;
- a clean-room adoption gate in which an external developer or coding agent
  creates a valid feature without changing RouteDeck core.

A second example is justified only when it proves a missing reusable
authoring boundary. It must not become a second product-development roadmap.

## M2: Semantic Observability

Objective: make every governed interaction explainable without exposing
private data or model chain of thought.

Outcomes:

- one correlated timeline across user, agent, surface, operation, review,
  handler, persistence, event, and browser synchronization boundaries;
- operation, provider, and guard decision evidence;
- public state and projection diffs;
- delivery classification for external effects;
- request identity, replay, lease, and convergence diagnostics;
- sanitized trace export suitable for local debugging and CI evidence.

This milestone extends RouteDeck's existing governance and inspection
responsibility. It does not turn RouteDeck into a general model-observability
platform.

## M3: Stable RouteDeck 1.0

Objective: stabilize the proven kernel rather than expand its domain scope.

Outcomes:

- stable public authoring and runtime contracts;
- semantic-versioning and compatibility policy;
- public conformance tests for consumers and adapters;
- measured performance and reliability budgets;
- security and release processes exercised by real external adoption;
- removal of accidental complexity identified by alpha users.

## Non-Goals

The roadmap does not commit RouteDeck core to:

- product authentication, user, tenant, or authorization systems;
- multi-agent orchestration or agent-to-agent protocols;
- product tool execution or business recovery policy;
- a model provider, prompt framework, or LangGraph replacement;
- a visual design system;
- MCP, A2A, AG-UI, or other protocol implementations without a proven
  consumer requirement and a separately approved dependency decision;
- additional Medusa commerce capabilities.

## Current Status

M0 public source preparation and GitHub publication are complete. The canonical
repository is
[`github.com/saastoagent/routedeck`](https://github.com/saastoagent/routedeck),
and its first corrective CI run is green. The completed implementation plan is
[archived](./docs/archive/2026-07-21-routedeck-public-alpha.md).

PyPI/npm publication remains incomplete. RouteDeck must not claim registry
availability until namespace ownership, trusted publishers, alpha versions,
publication, and clean registry installs are proven. M1 begins after that M0
package release; coverage hardening may continue independently.

## Changing The Roadmap

A roadmap change must start from a concrete consumer problem or verified
framework limitation. It must identify the RouteDeck boundary involved, show
why existing product/framework mechanisms are insufficient, and state the
smallest proof that would justify adding scope. Accepted architectural changes
still require an ADR; editing this roadmap cannot change framework contracts.
