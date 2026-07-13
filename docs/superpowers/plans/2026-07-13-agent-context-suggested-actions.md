# Agent Context And Suggested Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make RouteDeck resolve and inject trusted agent policies, supervise compact suggested actions, and allow conversation-only nodes without an active surface; migrate Medusa home to that architecture.

**Architecture:** RouteDeck Core owns typed declarations, compile-time reference validation, current-context resolution, and public projection. The LangGraph adapter renders trusted resolved policies separately from untrusted JSON state and continues to enforce the legal tool set structurally. RouteDeck React renders projected suggested actions and dispatches their bound operations; Medusa declares only product identity, checkout policy, identifiers, and business operations/surfaces.

**Tech Stack:** Python 3.12, Pydantic 2, LangGraph/LangChain middleware, React 19, TypeScript, Vitest, pytest.

## Global Constraints

- Run services and verification locally.
- Do not perform git operations.
- Do not add heuristic phrase matching, regex intent routing, canned responses, or product fallbacks.
- Treat projected session data as data, never as trusted prompt instructions.
- RouteDeck enforces legality and review; prompts explain behavior but never replace enforcement.
- Keep tests focused on the delivered behavior rather than running the broad release verifier.

---

### Task 1: Core contracts, compiler, and projection

**Files:**
- Create: `routedeck_core/contracts/agent.py`
- Modify: `routedeck_core/contracts/application.py`
- Modify: `routedeck_core/contracts/operations.py`
- Modify: `routedeck_core/contracts/surfaces.py`
- Modify: `routedeck_core/app/feature.py`
- Modify: `routedeck_core/app/compiled.py`
- Modify: `routedeck_core/app/compiler.py`
- Modify: `routedeck_core/contracts/projection.py`
- Modify: `routedeck_core/projection/projector.py`
- Test: `tests/app/test_agent_contracts.py`
- Test: `tests/projection/test_suggested_actions.py`

**Interfaces:**
- Produces: `AgentPolicySpec`, `AgentPolicyRef`, `SuggestedActionSpec`, `ProjectedSuggestedAction`.
- Produces: nullable `SurfaceSlotsSpec.active` and `ProjectedSurfaceSlots.active`.
- Produces: canonical `CompiledRouteDeckApp.agent_policies` and `PublicProjection.suggested_actions`.

- [ ] Write focused failing compiler tests showing that policy references are canonical and suggested actions must bind an operation declared on the same node.
- [ ] Run `python -m pytest tests/app/test_agent_contracts.py -q` and confirm failure is caused by missing contracts.
- [ ] Implement the typed declarations, canonical compiler catalog, stable reference validation, nullable active surface, and legal-operation-filtered suggested-action projection.
- [ ] Run `python -m pytest tests/app/test_agent_contracts.py tests/projection/test_suggested_actions.py -q` and confirm both files pass.

### Task 2: Context lens and LangGraph policy injection

**Files:**
- Create: `routedeck_core/context/agent.py`
- Modify: `routedeck_core/context/__init__.py`
- Modify: `routedeck_core/projection/policy.py`
- Modify: `routedeck_langgraph/model_context.py`
- Create: `routedeck_langgraph/prompt.py`
- Modify: `routedeck_langgraph/middleware.py`
- Test: `tests/test_langgraph_model_context.py`
- Test: `tests/test_langgraph_policy_prompt.py`

**Interfaces:**
- Produces: `AgentContextLens.resolve(session)` returning the current node, legal operations, optional active surface, visible entities, suggested actions, and stable deduplicated policies.
- Produces: `render_agent_system_message(existing, context)` that renders trusted policies before a clearly delimited JSON data block.

- [ ] Write focused failing tests for scoped policy resolution, policy deduplication/order, nullable surfaces, and trusted-policy/data separation.
- [ ] Run the two focused pytest files and confirm expected failures.
- [ ] Implement the lens, stable RouteDeck framework policies, model-context mapping, and adapter renderer.
- [ ] Re-run the two focused pytest files and confirm they pass.

### Task 3: React suggested-action primitive

**Files:**
- Modify: `packages/core/src/contracts/decode.ts`
- Regenerate: `packages/core/schema/routedeck.schema.json`
- Regenerate: `packages/core/src/contracts/generated.ts`
- Create: `packages/react/src/actions/RouteDeckSuggestedActions.tsx`
- Modify: `packages/react/src/surfaces/RouteDeckSurfaceHost.tsx`
- Modify: `packages/react/src/hooks/projection.ts`
- Modify: `packages/react/src/index.ts`
- Test: `packages/core/src/contracts/decode.test.ts`
- Test: `packages/react/src/actions/RouteDeckSuggestedActions.test.tsx`

**Interfaces:**
- Produces: decoded nullable `projection.surfaces.active` and `projection.suggested_actions`.
- Produces: `<RouteDeckSuggestedActions />`, which uses `useRouteDeckDispatch()` and never derives chips from all legal operations.

- [ ] Write focused failing decode and component tests for a nullable active surface and a supervised chip dispatch.
- [ ] Run only those test files and confirm expected failures.
- [ ] Regenerate transport types, implement strict decoding, skip null surfaces in the host, and add the suggested-action component.
- [ ] Run the focused tests plus package type checks.

### Task 4: Medusa migration

**Files:**
- Modify: `examples/medusa-agent/backend/medusa_agent/identifiers.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/catalog/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/checkout/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/agent.py`
- Delete: `examples/medusa-agent/frontend/src/app/BuyerWelcomeSurface.tsx`
- Modify: `examples/medusa-agent/frontend/src/routedeck/surfaces.tsx`
- Modify: `examples/medusa-agent/frontend/src/ui/AgentShell.tsx`
- Modify: `examples/medusa-agent/frontend/src/ui/Conversation.tsx`
- Modify: `examples/medusa-agent/frontend/src/app/app.css`
- Test: `examples/medusa-agent/backend/tests/contract/test_home_session.py`
- Test: `examples/medusa-agent/backend/tests/contract/test_agent_middleware.py`
- Test: `examples/medusa-agent/frontend/src/tests/app-shell.test.tsx`

**Interfaces:**
- Medusa home declares `buyer.browse_products` bound to `catalog.list` and has no active surface.
- The base prompt keeps only Medusa identity, tone, and model-generated greeting guidance; RouteDeck and checkout feature policies supply operational guidance.
- The conversation renders chips between messages and any real active surface.

- [ ] Change the focused Medusa contract tests first to require the chip, no home surface, and adapter-injected generic policies.
- [ ] Run those tests and confirm expected failures.
- [ ] Migrate the feature declarations, prompt, surface registry, conversation composition, and compact chip styling.
- [ ] Re-run the three focused Medusa test files and frontend type check.

### Task 5: Local behavior proof

**Files:**
- Verify only; no release-verifier changes.

**Interfaces:**
- Demonstrates: model-generated `Hi` at `buyer.home`, no automatic navigation, one Browse Products chip, supervised `catalog.list`, navigation to `/products`, and a real product-grid surface.

- [ ] Start the local stack with `& examples/medusa-agent/scripts/demo-stack.ps1 -Action Up -Services all` using the approved local OpenAI environment.
- [ ] Smoke `http://127.0.0.1:8098/api/medusa-agent/ready` and `http://127.0.0.1:5198/`.
- [ ] Exercise the full home-to-catalog path in the browser and capture concrete runtime evidence.
- [ ] Run the bounded backend and frontend checks once more, then report commands, URLs, behavior, and any remaining limitation.
