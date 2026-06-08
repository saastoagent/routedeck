# RouteDeck Medusa Reference Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align RouteDeck core and React contracts to `docs/route-deck-reference.md`, then complete the Medusa example as the public reference app that proves those contracts without product/framework leakage or hardcoded agent behavior.

**Architecture:** RouteDeck owns product-neutral projection, navgraph, capability, dispatch, surface, affordance, entity, diagnostics, introspection, and React client-store contracts. Medusa owns commerce data, prompts, product planning context, product agent execution, domain API calls, side effects, UI copy, and fixture reset behavior. Corpus/SaaStoAgent remains a compatibility gate after the RouteDeck + Medusa contract is green; it must not drive the canonical schema.

**Tech Stack:** Python, Pydantic, pytest, FastAPI, LangGraph, `langchain-openai`, React, TypeScript, Vite, Vitest, Testing Library, `@routedeck/react`, local/demo Medusa Store API.

---

## Authority And Context

Start every execution session by reading these files:

- `critical_prompt.md`
- `context.md`
- `docs/route-deck-reference.md`
- `docs/medusa-agent-reference-app.md`
- `work_prompt.md`
- `architecture/code-map.md`
- `test_index/README.md`

The contract authority for this plan is only:

1. `docs/route-deck-reference.md`

Use this read/update order after checking each file against the locked reference:

1. `routedeck_core/models.py`
2. `react/src/types.ts`
3. `examples/medusa-agent` product-owned adapter/runtime/planning context
4. derived docs and tests

Current known drift:

- `routedeck_core/models.py` has operations, surfaces, navigation, projection, dispatch, events, and introspection, but no explicit capability contract, navgraph payload, available/rendered/selectable entities, surface affordances, surface interaction event, or semantic observation models.
- `react/src/types.ts` mirrors the thinner core shape and lacks hooks for capabilities, affordances, and entity pools.
- `examples/medusa-agent/backend/services/routedeck_manifest.py` has Slice 3 nodes and actions, but no edges or `capability_id`s.
- `examples/medusa-agent/backend/services/routedeck_runtime.py` exposes sanitized opaque refs in surface props, but not a shared available-entity pool or declared affordances.
- `examples/medusa-agent/backend/services/routedeck_prompt.py` summarizes legal operation labels, but does not build product-owned planning context from entities and affordances.
- `examples/medusa-agent/frontend/src/App.tsx` dispatches operation IDs directly from surface rendering code instead of emitting declared surface affordance events.

## Non-Negotiable Boundaries

- Product graph truth stays in the product runtime.
- RouteDeck projection is output, not the graph source of truth.
- Surfaces present declared capabilities; they do not mutate graph state.
- Anything semantic a surface can do must also be available to chat through product-owned planning context.
- Product agents consume product-owned planning context derived from RouteDeck projection.
- RouteDeck does not own prompts, model calls, commerce policy, Medusa API calls, product copy, or phrase routing.
- Internal `route.*` operations stay hidden from ordinary product UI and product-agent planning context.
- Product-specific APIs stay product-owned. Do not add Medusa or other domain child paths under the generic RouteDeck API plane.
- No deterministic phrase-router fallback, alias table, command table, or hardcoded product response path may be presented as the agent.
- No hardcoded catalog. Runtime product names, variants, prices, images, regions, carts, and line items must come from the local/demo Medusa Store API or test doubles.

## Anti-Drift Gates

Every implementation task must preserve these gates:

- Framework source gate: `routedeck_core`, `routedeck_langgraph`, and `react/src` must not contain Medusa, SaaStoAgent, Corpus, cart fixture, product fixture, or domain-specific route behavior.
- API-plane gate: `/api/medusa-agent/*` remains product-owned; `/api/routedeck/*` remains generic framework projection/dispatch/inspect/stream. Medusa and other domain child paths must not appear under the RouteDeck API plane.
- Agent gate: no phrase map, alias router, command router, or deterministic natural-language fallback. The model selects against planning context; runtime validates.
- Affordance parity gate: every surface affordance that can change semantic state has a matching planning-context operation/entity path for chat.
- Entity binding gate: chat and surfaces use stable `entity_key`s and server-bindable opaque refs; public UI and chat text do not expose private Medusa `prod_*`, `variant_*`, `cart_*`, `line_*`, payment, or admin IDs.
- Hidden route gate: `route.open_node`, `route.switch_surface`, `route.back`, `route.forward`, and `route.cancel` may exist for framework/runtime plumbing, browser replay, diagnostics, and tests, but must not be ordinary shopper UI controls or product-agent planning operations.
- Reset fixture gate: Medusa writes remain local/demo fixture writes; later reset work must be explicit before open-source downloadable status.

Use these spot checks during execution:

```powershell
rg -n "api/routedeck/(medusa|propertydesk|corpus|saastoagent|checkout|cart|order|payment|shipping|fulfillment)|phrase_router|alias_router|command_router|intent_map" examples/medusa-agent routedeck_core react/src
rg -n "Medusa|medusa|cart|checkout|product_ref|variant_ref" routedeck_core react/src
rg -n "prod_|variant_|cart_|line_" examples/medusa-agent/frontend/src examples/medusa-agent/backend/services/routedeck_prompt.py examples/medusa-agent/backend/services/planning_context.py
```

The first command should produce no implementation hits. The second command should produce no framework hits. The third command should produce no public UI or prompt/planning text hits, except variable names that refer to opaque public refs only when tests explicitly cover hiding private IDs.

## File Structure

Framework contracts:

- Modify `routedeck_core/models.py`: add capability, navgraph, entity, affordance, surface-event, and semantic-observation models; extend projection and dispatch input compatibly.
- Modify `routedeck_core/runtime.py`: extend `build_projection(...)` to accept new optional contract fields and derive basic navgraph from manifest/topology when supplied.
- Modify `routedeck_core/__init__.py`: export new models.
- Modify `routedeck_core/validation.py`: validate capability/action/entity/affordance consistency.
- Modify `tests/test_core_contract.py`, `tests/test_projection_contract.py`, and `tests/test_runtime_store_contract.py`: protect new contract shape and backward compatibility.

React package:

- Modify `react/src/types.ts`: TypeScript parity for new core models.
- Modify `react/src/RouteDeckProvider.tsx`: add hooks for capabilities, entities, and affordances.
- Modify `react/src/RouteDeckStore.ts`: normalize new projection fields and preserve event/dispatch compatibility.
- Modify `react/src/index.ts`: export new types and hooks.
- Modify `react/tests/*.tsx` and `react/tests/*.mjs`: protect type exports, hooks, store normalization, and hidden route behavior.

Medusa example:

- Modify `examples/medusa-agent/backend/services/routedeck_manifest.py`: add capability IDs, manifest capabilities, and navgraph edges.
- Modify `examples/medusa-agent/backend/services/routedeck_runtime.py`: project available entities, rendered entities, surface affordances, and dispatch resolution from surface events.
- Create `examples/medusa-agent/backend/services/planning_context.py`: product-owned planning context derived from RouteDeck projection.
- Modify `examples/medusa-agent/backend/services/routedeck_prompt.py`: use planning context summaries, not raw RouteDeck internals.
- Modify `examples/medusa-agent/backend/services/agent_tools.py`: dispatch validated capability/entity requests through runtime.
- Modify `examples/medusa-agent/backend/services/chat_service.py` and `graph_builder.py`: pass session-aware planning context into the product agent.
- Modify `examples/medusa-agent/backend/routes/routedeck.py`: accept generic dispatch input that may carry a surface interaction event.
- Modify Medusa backend tests: `test_slice2_routedeck.py`, `test_slice3_routedeck_runtime.py`, `test_slice3_agent_tools.py`, and `test_slice1_chat.py`.
- Modify `examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts`: use full `@routedeck/react` types and expose `emitSurfaceInteraction(...)`.
- Modify `examples/medusa-agent/frontend/src/App.tsx`: render from surface props and emit affordance events; do not hardcode dispatch operation IDs in component rendering.
- Modify `examples/medusa-agent/frontend/src/App.test.tsx`: assert product UI behavior, no internals, no direct operation dispatch from components.

Docs and validation:

- Modify `docs/medusa-agent-reference-app.md`: add reference-aligned Slice 4 or "Slice 3 alignment" section.
- Modify `examples/medusa-agent/README.md`: explain the reference-aligned flow, local/demo Medusa requirements, and non-goals.
- Modify `docs/using-routedeck.md` if public adoption language changes.
- Modify `architecture/components/core-runtime-contract.md`, `architecture/components/react-runtime-debugger.md`, and `architecture/components/examples-and-adoption.md` if public interfaces change.
- Modify `test_index/README.md` when adding new commands or suites.
- Modify `tests/test_medusa_reference_slice0.py`: add anti-drift guards for the new contracts and example.

Corpus compatibility:

- Run `agent-lab-powered-projects/saastoagent-v0.1` Corpus tests after framework changes.
- Modify Corpus only if new optional fields require compatibility updates.
- Do not remodel Corpus planning context during the RouteDeck + Medusa readiness track unless tests prove a breaking contract gap.

## Task 0: Baseline And Guard Snapshot

**Files:**

- Read: all context and reference files listed above.
- No code changes.

- [ ] **Step 1: Confirm clean worktree**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core"
git status --short --branch
cd agent-lab-powered-projects\routedeck
git status --short --branch
```

Expected: no uncommitted user work. If there is unrelated user work, preserve it and do not overwrite it.

- [ ] **Step 2: Run current reference guard**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Expected: current guard passes before alignment starts. If it fails, fix the existing guard failure before adding new contract changes.

- [ ] **Step 3: Capture current downstream drift**

Run:

```powershell
rg -n "capability_id|surface_affordance|available_entities|planning_context|route\.|catalog.open|cart.add_item" routedeck_core react/src examples/medusa-agent tests
```

Expected: confirms current drift and gives a review anchor. Do not treat this command as a pass/fail test.

## Task 1: Core Contract RED Tests

**Files:**

- Modify: `tests/test_core_contract.py`
- Modify: `tests/test_projection_contract.py`
- Modify: `tests/test_runtime_store_contract.py`

- [ ] **Step 1: Add capability/entity/affordance model tests**

Add tests that describe the locked reference shape before implementation:

```python
def test_projection_contract_exposes_capabilities_entities_and_affordances():
    from routedeck_core import (
        RouteDeckAvailableEntity,
        RouteDeckBindingExpression,
        RouteDeckCapabilitySpec,
        RouteDeckLocation,
        RouteDeckNavigationState,
        RouteDeckOperation,
        RouteDeckProjection,
        RouteDeckSurface,
        RouteDeckSurfaceAffordance,
    )

    projection = RouteDeckProjection(
        current_context="detail",
        graph_node="detail",
        legal_operations=[
            RouteDeckOperation(
                id="cart.add_item",
                label="Add to cart",
                capability_id="cart.add_item",
                required_args=["variant_ref", "quantity"],
                missing_args=[],
                safety_class="write_external",
                execution_mode="review",
            )
        ],
        surfaces={
            "active": RouteDeckSurface(
                name="active",
                surface_id="detail.product_detail",
                component="MedusaProductDetail",
                variant="product_detail",
                role="active",
            )
        },
        navigation=RouteDeckNavigationState(
            current=RouteDeckLocation(node_id="detail", surface_id="detail.product_detail")
        ),
        capabilities=[
            RouteDeckCapabilitySpec(
                capability_id="cart.add_item",
                label="Add item to cart",
                operation_ids=["cart.add_item"],
                entity_kinds=["variant"],
                surface_ids=["detail.product_detail"],
                chat_enabled=True,
                surface_enabled=True,
            )
        ],
        available_entities=[
            RouteDeckAvailableEntity(
                kind="variant",
                entity_key="variant:s-black",
                label="S / Black",
                parent_label="Medusa T-Shirt",
                rendered_on=["detail.product_detail"],
                operations=[
                    {
                        "operation_id": "cart.add_item",
                        "args": {"variant_ref": "variant_opaque_1", "quantity": 1},
                    }
                ],
            )
        ],
        surface_affordances=[
            RouteDeckSurfaceAffordance(
                surface_id="detail.product_detail",
                affordance_id="add_to_cart",
                event="add_clicked",
                capability_id="cart.add_item",
                operation_id="cart.add_item",
                entity_key="variant:s-black",
                arg_bindings={
                    "variant_ref": RouteDeckBindingExpression(
                        source="entity",
                        path="operations.cart.add_item.args.variant_ref",
                    ),
                    "quantity": RouteDeckBindingExpression(source="event", path="quantity"),
                },
            )
        ],
    )

    payload = projection.model_dump(mode="json")
    assert payload["capabilities"][0]["capability_id"] == "cart.add_item"
    assert payload["available_entities"][0]["entity_key"] == "variant:s-black"
    assert payload["surface_affordances"][0]["arg_bindings"]["quantity"] == {
        "from": "event",
        "path": "quantity",
    }
```

- [ ] **Step 2: Add navgraph contract test**

```python
def test_projection_contract_exposes_navgraph_without_treating_actions_as_nodes():
    from routedeck_core import (
        RouteDeckLocation,
        RouteDeckNavGraph,
        RouteDeckNavGraphEdge,
        RouteDeckNavGraphNode,
        RouteDeckNavigationState,
        RouteDeckProjection,
    )

    projection = RouteDeckProjection(
        current_context="detail",
        graph_node="detail",
        navigation=RouteDeckNavigationState(current=RouteDeckLocation(node_id="detail")),
        navgraph=RouteDeckNavGraph(
            current=RouteDeckLocation(node_id="detail", surface_id="detail.product_detail"),
            nodes=[
                RouteDeckNavGraphNode(id="browse", label="Browse products"),
                RouteDeckNavGraphNode(id="detail", label="Product detail"),
                RouteDeckNavGraphNode(id="cart", label="Cart"),
            ],
            edges=[
                RouteDeckNavGraphEdge(source="browse", target="detail", action_id="catalog.open"),
                RouteDeckNavGraphEdge(source="detail", target="cart", action_id="cart.add_item"),
            ],
            traversed=["browse", "detail"],
            reachable=["browse", "cart"],
        ),
    )

    node_ids = {node.id for node in projection.navgraph.nodes}
    assert "catalog.open" not in node_ids
    assert projection.navgraph.edges[0].action_id == "catalog.open"
```

- [ ] **Step 3: Add dispatch surface-event compatibility test**

```python
def test_dispatch_input_can_carry_surface_interaction_event_without_private_refs():
    from routedeck_core import RouteDeckDispatchInput, RouteDeckSurfaceInteractionEvent

    request = RouteDeckDispatchInput(
        surface_event=RouteDeckSurfaceInteractionEvent(
            surface_id="detail.product_detail",
            affordance_id="add_to_cart",
            entity_key="variant:s-black",
            payload={"quantity": 1},
        ),
        context={"session_id": "session-1"},
    )

    payload = request.model_dump(mode="json", exclude_none=True)
    assert payload["surface_event"]["entity_key"] == "variant:s-black"
    assert "variant_" not in str(payload["surface_event"])
```

- [ ] **Step 4: Run RED**

Run:

```powershell
python -m pytest tests/test_core_contract.py tests/test_projection_contract.py tests/test_runtime_store_contract.py -q
```

Expected: fail because the new core models and projection fields do not exist.

## Task 2: Core Contract Implementation

**Files:**

- Modify: `routedeck_core/models.py`
- Modify: `routedeck_core/runtime.py`
- Modify: `routedeck_core/__init__.py`
- Modify: `routedeck_core/validation.py`

- [ ] **Step 1: Add product-neutral model classes**

Implement these names in `routedeck_core/models.py`:

```python
class RouteDeckCapabilitySpec(BaseModel):
    capability_id: str
    label: str
    operation_ids: list[str] = Field(default_factory=list)
    entity_kinds: list[str] = Field(default_factory=list)
    surface_ids: list[str] = Field(default_factory=list)
    chat_enabled: bool = True
    surface_enabled: bool = True
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDeckEntityOperationBinding(BaseModel):
    operation_id: str
    args: dict[str, Any] = Field(default_factory=dict)


class RouteDeckAvailableEntity(BaseModel):
    kind: str
    entity_key: str
    label: str
    parent_label: str | None = None
    rendered_on: list[str] = Field(default_factory=list)
    operations: list[RouteDeckEntityOperationBinding] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDeckBindingExpression(BaseModel):
    source: Literal["entity", "event"] = Field(alias="from")
    path: str

    model_config = {"populate_by_name": True}


class RouteDeckSurfaceAffordance(BaseModel):
    surface_id: str
    affordance_id: str
    event: str
    capability_id: str | None = None
    operation_id: str | None = None
    entity_key: str | None = None
    entity_keys: list[str] = Field(default_factory=list)
    arg_bindings: dict[str, RouteDeckBindingExpression] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDeckSurfaceInteractionEvent(BaseModel):
    surface_id: str
    affordance_id: str
    entity_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class RouteDeckSemanticObservation(BaseModel):
    observation_type: str = Field(alias="type")
    summary: str
    entity_key: str | None = None
    operation_id: str | None = None
    accepted: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class RouteDeckNavGraphNode(BaseModel):
    id: str
    label: str
    surface_id: str | None = None
    capability_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDeckNavGraphEdge(BaseModel):
    source: str = Field(alias="from")
    target: str = Field(alias="to")
    action_id: str | None = None
    capability_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class RouteDeckNavGraph(BaseModel):
    current: RouteDeckLocation
    nodes: list[RouteDeckNavGraphNode] = Field(default_factory=list)
    edges: list[RouteDeckNavGraphEdge] = Field(default_factory=list)
    traversed: list[str] = Field(default_factory=list)
    reachable: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Extend existing models compatibly**

Add these fields without breaking old payloads:

```python
class RouteDeckActionSpec(BaseModel):
    ...
    capability_id: str | None = None


class RouteDeckOperation(BaseModel):
    ...
    capability_id: str | None = None
    surface_id: str | None = None


class RouteDeckManifest(BaseModel):
    ...
    capabilities: list[RouteDeckCapabilitySpec] = Field(default_factory=list)


class RouteDeckProjection(BaseModel):
    ...
    capabilities: list[RouteDeckCapabilitySpec] = Field(default_factory=list)
    navgraph: RouteDeckNavGraph | None = None
    available_entities: list[RouteDeckAvailableEntity] = Field(default_factory=list)
    surface_affordances: list[RouteDeckSurfaceAffordance] = Field(default_factory=list)


class RouteDeckDispatchInput(BaseModel):
    operation_id: str | None = None
    surface_event: RouteDeckSurfaceInteractionEvent | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    graph_state: dict[str, Any] = Field(default_factory=dict)
    projection_version: int | None = None
    context: dict[str, Any] = Field(default_factory=dict)
```

Keep old callers valid by allowing `operation_id` exactly as before.

- [ ] **Step 3: Extend `build_projection(...)`**

Add optional parameters:

```python
capabilities: list[RouteDeckCapabilitySpec] | None = None
navgraph: RouteDeckNavGraph | dict[str, Any] | None = None
available_entities: list[RouteDeckAvailableEntity] | None = None
surface_affordances: list[RouteDeckSurfaceAffordance] | None = None
```

Set defaults to manifest capabilities and empty lists. Do not infer product entities in core.

- [ ] **Step 4: Validate product-neutral consistency**

Extend `validate_manifest(...)` to report:

- action references unknown capability
- node references unknown capability
- edge `action_id` references unknown action
- edge `capability_id` references unknown capability

Do not require every action to have a capability yet; existing examples must remain valid during migration.

- [ ] **Step 5: Export all new models**

Update `routedeck_core/__init__.py` so tests and downstream users can import the new names from `routedeck_core`.

- [ ] **Step 6: Run GREEN**

Run:

```powershell
python -m pytest tests/test_core_contract.py tests/test_projection_contract.py tests/test_runtime_store_contract.py -q
```

Expected: tests pass.

## Task 3: React Contract RED Tests And Implementation

**Files:**

- Modify: `react/src/types.ts`
- Modify: `react/src/RouteDeckProvider.tsx`
- Modify: `react/src/RouteDeckStore.ts`
- Modify: `react/src/index.ts`
- Modify: `react/tests/store-contract.tsx`
- Modify: `react/tests/runtime-contract.tsx`
- Create or modify: `react/tests/projection-contract.test.mjs`

- [ ] **Step 1: Add type/hook tests**

Add a React type contract test that imports and uses:

```tsx
import {
  RouteDeckProvider,
  useRouteDeckAvailableEntities,
  useRouteDeckCapabilities,
  useRouteDeckSurfaceAffordances,
  type RouteDeckAvailableEntity,
  type RouteDeckCapabilitySpec,
  type RouteDeckProjection,
  type RouteDeckSurfaceAffordance,
} from '../src'
```

Use this projection shape:

```tsx
const projection: RouteDeckProjection = {
  current_context: 'detail',
  graph_node: 'detail',
  projection_version: 1,
  legal_operations: [],
  capabilities: [
    {
      capability_id: 'cart.add_item',
      label: 'Add item to cart',
      operation_ids: ['cart.add_item'],
      entity_kinds: ['variant'],
      surface_ids: ['detail.product_detail'],
      chat_enabled: true,
      surface_enabled: true,
    } satisfies RouteDeckCapabilitySpec,
  ],
  surfaces: {
    active: {
      name: 'active',
      surface_id: 'detail.product_detail',
      component: 'MedusaProductDetail',
      variant: 'product_detail',
      role: 'active',
    },
  },
  available_entities: [
    {
      kind: 'variant',
      entity_key: 'variant:s-black',
      label: 'S / Black',
      rendered_on: ['detail.product_detail'],
      operations: [{ operation_id: 'cart.add_item', args: { variant_ref: 'variant_opaque_1' } }],
    } satisfies RouteDeckAvailableEntity,
  ],
  surface_affordances: [
    {
      surface_id: 'detail.product_detail',
      affordance_id: 'add_to_cart',
      event: 'add_clicked',
      capability_id: 'cart.add_item',
      operation_id: 'cart.add_item',
      entity_key: 'variant:s-black',
      arg_bindings: { quantity: { from: 'event', path: 'quantity' } },
    } satisfies RouteDeckSurfaceAffordance,
  ],
  presentation_state: {},
  navigation: { current: { node_id: 'detail', surface_id: 'detail.product_detail' }, back_stack: [], forward_stack: [], can_back: false, can_forward: false, can_cancel: false },
  diagnostics: {},
}
```

- [ ] **Step 2: Implement TypeScript parity**

Add TypeScript interfaces mirroring the Python models:

- `RouteDeckCapabilitySpec`
- `RouteDeckEntityOperationBinding`
- `RouteDeckAvailableEntity`
- `RouteDeckBindingExpression`
- `RouteDeckSurfaceAffordance`
- `RouteDeckSurfaceInteractionEvent`
- `RouteDeckSemanticObservation`
- `RouteDeckNavGraphNode`
- `RouteDeckNavGraphEdge`
- `RouteDeckNavGraph`

Extend `RouteDeckOperation`, `RouteDeckManifest`, `RouteDeckProjection`, and `RouteDeckDispatchInput` in parity with core.

- [ ] **Step 3: Add hooks**

Add these hooks in `RouteDeckProvider.tsx`:

```tsx
export function useRouteDeckCapabilities(): RouteDeckCapabilitySpec[] {
  return useRouteDeckProjection().capabilities || []
}

export function useRouteDeckCapability(capabilityId: string): RouteDeckCapabilitySpec | null {
  const capabilities = useRouteDeckCapabilities()
  return useMemo(
    () => capabilities.find((capability) => capability.capability_id === capabilityId) || null,
    [capabilities, capabilityId],
  )
}

export function useRouteDeckAvailableEntities(): RouteDeckAvailableEntity[] {
  return useRouteDeckProjection().available_entities || []
}

export function useRouteDeckSurfaceAffordances(surfaceId?: string | null): RouteDeckSurfaceAffordance[] {
  const affordances = useRouteDeckProjection().surface_affordances || []
  return useMemo(
    () => surfaceId ? affordances.filter((affordance) => affordance.surface_id === surfaceId) : affordances,
    [affordances, surfaceId],
  )
}
```

- [ ] **Step 4: Normalize projection defaults**

Update `normalizeProjection(...)` in `RouteDeckStore.ts` so missing new fields become empty lists and old payloads keep working.

- [ ] **Step 5: Export new types and hooks**

Update `react/src/index.ts` with the new hooks and type exports.

- [ ] **Step 6: Run React tests**

Run:

```powershell
cd react
npm test
```

Expected: React tests pass.

## Task 4: Medusa Manifest And Projection RED Tests

**Files:**

- Modify: `examples/medusa-agent/backend/tests/test_slice3_routedeck_runtime.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice3_agent_tools.py`
- Modify: `tests/test_medusa_reference_slice0.py`

- [ ] **Step 1: Add manifest capability and edge tests**

```python
def test_medusa_manifest_declares_capabilities_and_navgraph_edges():
    from services.routedeck_manifest import SLICE3_MANIFEST

    capabilities = {capability.capability_id: capability for capability in SLICE3_MANIFEST.capabilities}
    assert {"catalog.browse", "catalog.detail", "variant.select", "cart.add_item", "cart.view"} <= set(capabilities)

    edge_pairs = {(edge.from_stage, edge.to_stage, edge.action_id) for edge in SLICE3_MANIFEST.edges}
    assert ("browse", "detail", "catalog.open") in edge_pairs
    assert ("detail", "cart", "cart.add_item") in edge_pairs

    node_ids = {node.id for node in SLICE3_MANIFEST.nodes}
    assert "catalog.open" not in node_ids
```

- [ ] **Step 2: Add projection entity/affordance tests**

```python
@pytest.mark.asyncio
async def test_ready_projection_exposes_entities_and_surface_affordances(monkeypatch):
    from core.config import Settings
    from services.medusa_store import StoreProduct, StoreVariant
    from services.routedeck_runtime import MedusaRouteDeckRuntime

    async def fake_setup(_settings, timeout=2.0):
        return {"setup": {"ready": True, "mode": "local-demo"}, "connections": []}

    class FakeStoreClient:
        async def list_products(self, limit=12):
            return [
                StoreProduct(
                    id="prod_private",
                    title="Medusa T-Shirt",
                    variants=[StoreVariant(id="variant_private", title="S / Black")],
                )
            ]

    monkeypatch.setattr("services.routedeck_runtime.probe_medusa_setup", fake_setup)
    runtime = MedusaRouteDeckRuntime(
        settings=Settings(medusa_publishable_api_key="pk_test"),
        store_client=FakeStoreClient(),
    )

    projection = await runtime.projection({"session_id": "s1"})
    payload = projection.model_dump(mode="json")

    assert payload["capabilities"]
    assert payload["navgraph"]["current"]["node_id"] == "browse"
    assert payload["available_entities"][0]["kind"] == "product"
    assert payload["available_entities"][0]["entity_key"].startswith("product:")
    assert payload["surface_affordances"][0]["surface_id"] == "browse.product_list"
    assert "prod_private" not in str(payload)
    assert "variant_private" not in str(payload)
```

- [ ] **Step 3: Add parity test between affordances and planning context**

```python
@pytest.mark.asyncio
async def test_surface_affordances_are_chat_doable(monkeypatch):
    from services.planning_context import build_medusa_planning_context

    projection = await _ready_projection_with_product(monkeypatch)
    planning_context = build_medusa_planning_context(projection)

    affordance_ops = {
        affordance.operation_id
        for affordance in projection.surface_affordances
        if affordance.operation_id
    }
    planning_ops = {operation["id"] for operation in planning_context["legal_operations"]}
    assert affordance_ops <= planning_ops
    assert planning_context["available_entities"]
    assert planning_context["surface_affordances"]
```

Implement `_ready_projection_with_product(...)` as a local test helper using mocked setup and mocked Store API, not real network.

- [ ] **Step 4: Run RED**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice3_routedeck_runtime.py tests/test_slice3_agent_tools.py -q
cd ..\..\..
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Expected: fail until Medusa manifest/runtime/planning context is aligned.

## Task 5: Medusa Manifest And Runtime Alignment

**Files:**

- Modify: `examples/medusa-agent/backend/services/routedeck_manifest.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_runtime.py`

- [ ] **Step 1: Add capability specs**

Define capabilities in `SLICE3_MANIFEST`:

```python
capabilities=[
    RouteDeckCapabilitySpec(
        capability_id="catalog.browse",
        label="Browse products",
        operation_ids=["catalog.list"],
        entity_kinds=["product"],
        surface_ids=["browse.product_list"],
    ),
    RouteDeckCapabilitySpec(
        capability_id="catalog.detail",
        label="View product details",
        operation_ids=["catalog.open"],
        entity_kinds=["product"],
        surface_ids=["browse.product_list", "detail.product_detail"],
    ),
    RouteDeckCapabilitySpec(
        capability_id="variant.select",
        label="Select variant",
        operation_ids=["variant.select"],
        entity_kinds=["variant"],
        surface_ids=["detail.product_detail"],
    ),
    RouteDeckCapabilitySpec(
        capability_id="cart.add_item",
        label="Add item to cart",
        operation_ids=["variant.select", "cart.add_item"],
        entity_kinds=["variant"],
        surface_ids=["detail.product_detail"],
    ),
    RouteDeckCapabilitySpec(
        capability_id="cart.view",
        label="View cart",
        operation_ids=["cart.view"],
        entity_kinds=["cart", "cart_item"],
        surface_ids=["cart.cart_summary"],
    ),
]
```

- [ ] **Step 2: Add `capability_id`s to nodes and actions**

Examples:

```python
RouteDeckNodeSpec(... id="browse", capability_id="catalog.browse", ...)
RouteDeckActionSpec(id="catalog.open", label="View product", capability_id="catalog.detail", category="navigation")
RouteDeckActionSpec(id="cart.add_item", label="Add selected item to cart", capability_id="cart.add_item", category="execution")
```

- [ ] **Step 3: Add navgraph edges**

Use real topology edges:

```python
edges=[
    RouteDeckEdgeSpec(from_stage="browse", to_stage="detail", type="action", action_id="catalog.open", capability_id="catalog.detail"),
    RouteDeckEdgeSpec(from_stage="detail", to_stage="browse", type="action", action_id="catalog.list", capability_id="catalog.browse"),
    RouteDeckEdgeSpec(from_stage="detail", to_stage="cart", type="action", action_id="cart.add_item", capability_id="cart.add_item"),
    RouteDeckEdgeSpec(from_stage="browse", to_stage="cart", type="action", action_id="cart.view", capability_id="cart.view"),
    RouteDeckEdgeSpec(from_stage="cart", to_stage="browse", type="action", action_id="catalog.list", capability_id="catalog.browse"),
]
```

- [ ] **Step 4: Project available entities**

In `MedusaRouteDeckRuntime`, add a separate entity-key store and helpers:

```python
self.entity_keys = OpaqueRefStore(prefix="entity")
```

The entity-key store is distinct from the existing product, variant, cart, and line ref stores.

```python
def _product_entity(self, product: StoreProduct, *, rendered_on: list[str]) -> RouteDeckAvailableEntity:
    entity_key = f"product:{self.entity_keys.remember(f'product:{product.id}')}"
    product_ref = self.product_refs.remember(product.id)
    return RouteDeckAvailableEntity(
        kind="product",
        entity_key=entity_key,
        label=product.title,
        rendered_on=rendered_on,
        operations=[
            RouteDeckEntityOperationBinding(
                operation_id="catalog.open",
                args={"product_ref": product_ref},
            )
        ],
    )


def _variant_entity(self, product: StoreProduct, variant: StoreVariant, *, rendered_on: list[str]) -> RouteDeckAvailableEntity:
    entity_key = f"variant:{self.entity_keys.remember(f'variant:{variant.id}')}"
    variant_ref = self.variant_refs.remember(variant.id)
    return RouteDeckAvailableEntity(
        kind="variant",
        entity_key=entity_key,
        label=variant.title,
        parent_label=product.title,
        rendered_on=rendered_on,
        operations=[
            RouteDeckEntityOperationBinding(operation_id="variant.select", args={"variant_ref": variant_ref}),
            RouteDeckEntityOperationBinding(operation_id="cart.add_item", args={"variant_ref": variant_ref, "quantity": 1}),
        ],
    )
```

Do not use product name phrase maps. Entity keys and dispatch refs must be separate bindings:

- `entity_key` is a stable context-local key for UI and agent binding.
- `product_ref`, `variant_ref`, `cart_ref`, and `line_ref` are opaque runtime dispatch args.
- Do not derive an entity key by formatting a dispatch ref. Tests should make accidental equality between entity keys and opaque refs impossible.

- [ ] **Step 5: Project surface affordances**

For product list:

```python
RouteDeckSurfaceAffordance(
    surface_id="browse.product_list",
    affordance_id="view_product",
    event="view_clicked",
    capability_id="catalog.detail",
    operation_id="catalog.open",
    entity_keys=[entity.entity_key for entity in product_entities],
    arg_bindings={
        "product_ref": RouteDeckBindingExpression(
            source="entity",
            path="operations.catalog.open.args.product_ref",
        )
    },
)
```

For product detail:

```python
RouteDeckSurfaceAffordance(
    surface_id="detail.product_detail",
    affordance_id="select_variant",
    event="variant_clicked",
    capability_id="variant.select",
    operation_id="variant.select",
    entity_keys=[entity.entity_key for entity in variant_entities],
    arg_bindings={
        "variant_ref": RouteDeckBindingExpression(
            source="entity",
            path="operations.variant.select.args.variant_ref",
        )
    },
)
RouteDeckSurfaceAffordance(
    surface_id="detail.product_detail",
    affordance_id="add_to_cart",
    event="add_clicked",
    capability_id="cart.add_item",
    operation_id="cart.add_item",
    entity_keys=[entity.entity_key for entity in variant_entities],
    arg_bindings={
        "variant_ref": RouteDeckBindingExpression(
            source="entity",
            path="operations.cart.add_item.args.variant_ref",
        ),
        "quantity": RouteDeckBindingExpression(source="event", path="quantity"),
    },
)
```

- [ ] **Step 6: Sanitize surface props**

Change product props from opaque-ref-first shape to entity-key-first shape:

```python
{
    "entity_key": product_entity.entity_key,
    "title": product.title,
    "description": product.description,
    "thumbnail": product.thumbnail,
    "variants": [
        {
            "entity_key": variant_entity.entity_key,
            "title": variant.title,
            "options": variant.options,
        }
        for variant_entity, variant in variant_pairs
    ],
}
```

The frontend may hold entity keys. It must not need private Medusa IDs.

- [ ] **Step 7: Resolve surface events server-side**

Add a method:

```python
def _dispatch_input_from_surface_event(
    self,
    projection: RouteDeckProjection,
    event: RouteDeckSurfaceInteractionEvent,
) -> RouteDeckDispatchInput:
    affordance = next(
        (
            candidate
            for candidate in projection.surface_affordances
            if candidate.surface_id == event.surface_id and candidate.affordance_id == event.affordance_id
        ),
        None,
    )
    if affordance is None or affordance.operation_id is None:
        raise ValueError("Surface action is not available from the current projection.")
    allowed_entity_keys = set(affordance.entity_keys)
    if affordance.entity_key:
        allowed_entity_keys.add(affordance.entity_key)
    if event.entity_key and allowed_entity_keys and event.entity_key not in allowed_entity_keys:
        raise ValueError("Surface action is not available for that entity.")
    entity = next(
        (
            candidate
            for candidate in projection.available_entities
            if candidate.entity_key == event.entity_key
        ),
        None,
    )
    args = self._resolve_affordance_args(affordance, entity, event.payload)
    return RouteDeckDispatchInput(operation_id=affordance.operation_id, args=args)
```

Implement `_resolve_affordance_args(...)` by reading only from the matched entity's operation bindings and the event payload. Reject missing or mismatched entity bindings when any arg binding uses `from="entity"`, and reject entities that do not expose the affordance operation. Do not scan private Store API data or parse user text.

Add negative tests for:

- a valid affordance with an entity key that is not listed on that affordance
- an affordance/entity pair where the entity does not expose the target operation
- an entity-bound affordance event with no entity key

- [ ] **Step 8: Update `dispatch(...)`**

If `request.surface_event` is present:

1. Build current projection for the session.
2. Resolve the event to a typed `RouteDeckDispatchInput`.
3. Continue through the same operation dispatch path.

This keeps UI and chat on the same validation path.

- [ ] **Step 9: Run Medusa backend GREEN**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice3_routedeck_runtime.py -q
```

Expected: Medusa manifest/projection/runtime tests pass.

## Task 6: Product-Owned Planning Context And Agent Tools

**Files:**

- Create: `examples/medusa-agent/backend/services/planning_context.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_prompt.py`
- Modify: `examples/medusa-agent/backend/services/agent_tools.py`
- Modify: `examples/medusa-agent/backend/services/chat_service.py`
- Modify: `examples/medusa-agent/backend/services/graph_builder.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice3_agent_tools.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice1_chat.py`

- [ ] **Step 1: Add planning-context tests**

```python
def test_medusa_planning_context_hides_route_ops_and_exposes_entities():
    from services.planning_context import build_medusa_planning_context

    context = build_medusa_planning_context(_projection_with_entities_and_hidden_route_ops())

    assert context["current"]["node_id"] == "detail"
    assert {operation["id"] for operation in context["legal_operations"]} == {"variant.select", "cart.add_item"}
    assert context["available_entities"][0]["entity_key"].startswith("variant:")
    assert context["surface_affordances"][0]["affordance_id"] == "add_to_cart"
    assert "route.switch_surface" not in str(context)
    assert "prod_" not in str(context)
    assert "variant_private" not in str(context)
```

- [ ] **Step 2: Implement `build_medusa_planning_context(...)`**

Shape:

```python
def build_medusa_planning_context(projection: RouteDeckProjection) -> dict[str, Any]:
    current = projection.navigation.current
    legal_operations = [
        _operation_summary(operation)
        for operation in projection.legal_operations
        if not operation.id.startswith("route.") and operation.invocation_kind != "hidden"
    ]
    return {
        "current": {
            "node_id": current.node_id,
            "surface_id": current.surface_id,
        },
        "legal_operations": legal_operations,
        "surface_options": _surface_options(projection),
        "available_entities": [_entity_summary(entity) for entity in projection.available_entities],
        "surface_affordances": [_affordance_summary(affordance) for affordance in projection.surface_affordances],
        "missing_arguments": {
            operation.id: list(operation.missing_args)
            for operation in projection.legal_operations
            if operation.missing_args and not operation.id.startswith("route.")
        },
    }
```

Planning context is product-owned. Do not add this shape to `routedeck_core`.

- [ ] **Step 3: Update prompt construction**

`build_routedeck_system_prompt(...)` should:

- include current node/surface labels in product-safe language
- include legal product operation labels
- include available entity labels and entity keys for binding
- include affordance IDs and operation labels for the model planner
- exclude raw Medusa private IDs
- exclude hidden `route.*` operations
- exclude endpoint paths and diagnostics

Use wording that says "planning context" or "available shopping context" to the model. Do not expose RouteDeck internals in shopper-visible responses.

- [ ] **Step 4: Update agent tools**

Keep app-owned tools but make them planning-context aware. The tool implementation may accept:

```python
async def invoke_shopping_operation(operation_id: str, entity_key: str | None = None, quantity: int | None = None) -> str:
    projection = await runtime.projection({"session_id": session_id})
    planning_context = build_medusa_planning_context(projection)
    request = resolve_chat_capability_request(
        projection=projection,
        operation_id=operation_id,
        entity_key=entity_key,
        payload={"quantity": quantity} if quantity is not None else {},
    )
    result = await runtime.dispatch(request, context={"session_id": session_id, "source": "agent_tool"})
    return product_language_summary(result)
```

`resolve_chat_capability_request(...)` must match only current available entities and legal operations. It must return a clarification/guard if entity binding is missing or ambiguous. It must not use phrase maps or scan private Store API data.

- [ ] **Step 5: Preserve session threading**

Ensure `conversation_id` still maps to RouteDeck `session_id` and LangGraph `configurable.thread_id`.

- [ ] **Step 6: Run agent tests**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice1_chat.py tests/test_slice3_agent_tools.py -q
```

Expected: chat and tool tests pass without network.

## Task 7: Medusa Frontend Affordance Flow

**Files:**

- Modify: `examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts`
- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`
- Modify: `examples/medusa-agent/frontend/src/styles.css` only if layout needs minor adjustment.

- [ ] **Step 1: Add frontend RED tests**

Test that product list click emits a surface event:

```tsx
test("view product emits a surface affordance event instead of direct operation args", async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (String(url).includes("/api/routedeck/projection")) {
      return new Response(JSON.stringify({
        current_context: "browse",
        graph_node: "browse",
        projection_version: 1,
        legal_operations: [{ id: "catalog.open", label: "View product" }],
        surfaces: {
          active: {
            name: "active",
            surface_id: "browse.product_list",
            variant: "product_list",
            props: {
              products: [{ entity_key: "product:entity-1", title: "Medusa T-Shirt" }],
            },
          },
        },
        available_entities: [
          {
            kind: "product",
            entity_key: "product:entity-1",
            label: "Medusa T-Shirt",
            rendered_on: ["browse.product_list"],
            operations: [{ operation_id: "catalog.open", args: { product_ref: "product_opaque_1" } }],
          },
        ],
        surface_affordances: [
          {
            surface_id: "browse.product_list",
            affordance_id: "view_product",
            event: "view_clicked",
            operation_id: "catalog.open",
            entity_keys: ["product:entity-1"],
          },
        ],
        presentation_state: {},
        navigation: { current: { node_id: "browse", surface_id: "browse.product_list" }, back_stack: [], forward_stack: [] },
        diagnostics: {},
      }))
    }
    if (url === "/api/routedeck/dispatch") {
      expect(JSON.parse(String(init?.body))).toMatchObject({
        surface_event: {
          surface_id: "browse.product_list",
          affordance_id: "view_product",
          entity_key: "product:entity-1",
          payload: {},
        },
      })
      return new Response(JSON.stringify({ accepted: true }))
    }
    return new Response("{}", { status: 404 })
  })
  vi.stubGlobal("fetch", fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole("button", { name: /view medusa t-shirt/i }))

  expect(fetchMock).toHaveBeenCalledWith("/api/routedeck/dispatch", expect.objectContaining({ method: "POST" }))
})
```

- [ ] **Step 2: Use `@routedeck/react` types**

Replace local partial projection types where practical:

```ts
import type { RouteDeckProjection, RouteDeckSurfaceInteractionEvent } from "@routedeck/react"
```

If package linking makes direct import awkward inside the example, keep a local adapter type that exactly matches `react/src/types.ts` and add a test comment explaining why.

- [ ] **Step 3: Add `emitSurfaceInteraction(...)`**

In the hook:

```ts
const emitSurfaceInteraction = useCallback(
  async (surfaceEvent: RouteDeckSurfaceInteractionEvent) => {
    const response = await fetch("/api/routedeck/dispatch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        surface_event: surfaceEvent,
        context: { session_id: sessionId, source: "ui" },
      }),
    })
    if (!response.ok) {
      throw new Error(`RouteDeck surface action failed: ${response.status}`)
    }
    await refresh()
  },
  [refresh, sessionId],
)
```

Keep `dispatch(...)` only if tests or debugging still need direct operation dispatch. Ordinary product UI must use `emitSurfaceInteraction(...)`.

- [ ] **Step 4: Update product components**

Product card:

```tsx
onView={() =>
  emitSurfaceInteraction({
    surface_id: surface.surface_id || "browse.product_list",
    affordance_id: "view_product",
    entity_key: product.entity_key,
    payload: {},
  })
}
```

Variant select and add to cart:

```tsx
onClick={() =>
  emitSurfaceInteraction({
    surface_id: surface.surface_id || "detail.product_detail",
    affordance_id: "select_variant",
    entity_key: variant.entity_key,
    payload: {},
  })
}
```

```tsx
onClick={() =>
  selectedEntityKey &&
  emitSurfaceInteraction({
    surface_id: surface.surface_id || "detail.product_detail",
    affordance_id: "add_to_cart",
    entity_key: selectedEntityKey,
    payload: { quantity: 1 },
  })
}
```

Do not render entity keys, opaque refs, operation IDs, graph nodes, endpoint paths, diagnostics, or dispatch traces.

- [ ] **Step 5: Run frontend tests**

Run:

```powershell
cd examples/medusa-agent/frontend
npm test
```

Expected: frontend tests pass.

## Task 8: Anti-Drift Guard Tests

**Files:**

- Modify: `tests/test_medusa_reference_slice0.py`

- [ ] **Step 1: Add framework product-leak guard**

```python
def test_framework_contracts_do_not_absorb_medusa_product_behavior():
    text = _combined_text("routedeck_core", "routedeck_langgraph", "react/src")
    banned = [
        "Medusa",
        "medusa",
        "cart.add_item",
        "catalog.open",
        "product_ref",
        "variant_ref",
        "/api/medusa-agent",
    ]
    for needle in banned:
        assert needle not in text
```

- [ ] **Step 2: Add Medusa reference-alignment guard**

```python
def test_medusa_example_uses_reference_aligned_entities_and_affordances():
    text = _combined_text("examples/medusa-agent/backend", "examples/medusa-agent/frontend/src")
    assert "RouteDeckCapabilitySpec" in text
    assert "RouteDeckAvailableEntity" in text
    assert "RouteDeckSurfaceAffordance" in text
    assert "RouteDeckSurfaceInteractionEvent" in text
    assert "build_medusa_planning_context" in text
    assert not re.search(r"api/routedeck/(medusa|checkout|cart|order|payment|shipping|fulfillment)", text, re.I)
```

- [ ] **Step 3: Add no-hardcoded-agent guard**

```python
def test_medusa_agent_has_no_deterministic_phrase_router_or_fake_catalog():
    text = _combined_text(
        "examples/medusa-agent/backend/services",
        "examples/medusa-agent/backend/routes",
        "examples/medusa-agent/frontend/src",
    ).lower()
    banned = [
        "phrase_router",
        "alias_router",
        "command_router",
        "intent_map",
        "if message",
        "elif message",
        "hardcoded products",
        "fake catalog",
    ]
    for needle in banned:
        assert needle not in text
```

If this catches legitimate conditionals in SSE parsing or tests, narrow the scanned paths rather than weakening the rule.

- [ ] **Step 4: Add affordance parity guard**

```python
@pytest.mark.asyncio
async def test_medusa_surface_affordances_are_reflected_in_planning_context(monkeypatch):
    from services.planning_context import build_medusa_planning_context

    projection = await _ready_projection_with_product(monkeypatch)
    planning_context = build_medusa_planning_context(projection)

    planning_ops = {operation["id"] for operation in planning_context["legal_operations"]}
    planning_entities = {entity["entity_key"] for entity in planning_context["available_entities"]}
    planning_affordances = {
        (affordance["surface_id"], affordance["affordance_id"])
        for affordance in planning_context["surface_affordances"]
    }

    for affordance in projection.surface_affordances:
        if affordance.operation_id:
            assert affordance.operation_id in planning_ops
        assert (affordance.surface_id, affordance.affordance_id) in planning_affordances
        for entity_key in affordance.entity_keys or ([affordance.entity_key] if affordance.entity_key else []):
            assert entity_key in planning_entities

    assert "route.switch_surface" not in str(planning_context)
```

Reuse or promote the mocked projection helper from Task 4 so this guard proves behavior, not string presence.

- [ ] **Step 5: Run root guard**

Run:

```powershell
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Expected: root anti-drift guard passes.

## Task 9: Documentation And Public Readiness Update

**Files:**

- Modify: `docs/medusa-agent-reference-app.md`
- Modify: `examples/medusa-agent/README.md`
- Modify: `docs/using-routedeck.md` if framework usage language changes.
- Modify: `architecture/components/core-runtime-contract.md`
- Modify: `architecture/components/react-runtime-debugger.md`
- Modify: `architecture/components/examples-and-adoption.md`
- Modify: `test_index/README.md`
- Modify: `architecture/code-map.md` only if source ownership rows change.

- [ ] **Step 1: Update Medusa spec**

Add a section titled `Reference-Aligned Slice 3 Completion`:

```markdown
### Reference-Aligned Slice 3 Completion

Purpose: align the incomplete Slice 3 browse/detail/cart behavior to
`docs/route-deck-reference.md` before adding checkout, admin, or Docker scope.

Required additions:

- manifest capabilities and navgraph edges
- available/rendered/selectable entity pool
- declared surface affordances
- product-owned planning context derived from RouteDeck projection
- UI surface events resolved by the product runtime
- chat capability requests resolved through the same entity/operation bindings
- anti-drift guards for hidden route operations, product-specific RouteDeck
  routes, private ID leaks, phrase routers, and fake catalog data
```

- [ ] **Step 2: Update README run and validation sections**

Document:

- backend setup
- frontend setup
- required local/demo Medusa env vars
- behavior with Medusa unavailable
- behavior with Medusa available
- no checkout/payment/shipping/admin scope in this readiness track
- no product-specific RouteDeck routes
- no deterministic phrase router

- [ ] **Step 3: Update architecture component docs**

`core-runtime-contract.md` should mention:

- capabilities
- navgraph
- entity pool
- surface affordances
- surface interaction event
- semantic observation

`react-runtime-debugger.md` should mention:

- new type exports
- entity/affordance hooks
- store normalization of new projection fields

`examples-and-adoption.md` should mention:

- Medusa as product-specific reference example
- Medusa product behavior remains inside `examples/medusa-agent`
- generic RouteDeck API plane remains product-neutral

- [ ] **Step 4: Update validation index**

Add new focused commands if new tests are added:

```powershell
python -m pytest tests/test_core_contract.py tests/test_projection_contract.py tests/test_runtime_store_contract.py -q
cd react && npm test
cd examples/medusa-agent/backend && python -m pytest tests -q
cd examples/medusa-agent/frontend && npm test
python -m pytest tests/test_medusa_reference_slice0.py -q
```

## Task 10: Corpus Compatibility Gate

**Files:**

- Prefer no changes.
- Modify `agent-lab-powered-projects/saastoagent-v0.1` only if framework compatibility tests fail.

- [ ] **Step 1: Run Corpus boundary tests**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\saastoagent-v0.1"
python -m pytest backend/tests/test_app_graph_contract.py backend/tests/test_corpus_graph_contract.py backend/tests/test_corpus_routedeck_runtime.py backend/tests/test_corpus_routedeck_state.py backend/tests/test_corpus_turn_planning.py -q
```

Expected: pass without Corpus changes because new core fields are optional and defaulted.

- [ ] **Step 2: If tests fail, make compatibility-only edits**

Allowed edits:

- add default empty lists for new projection fields where Corpus constructs projections manually
- update TypeScript compile errors from new optional fields
- preserve `CorpusRouteDeckRuntime`
- preserve `/api/corpus/*`
- preserve hidden internal route filtering
- preserve `saasAgentUiStore` as UI-only local state

Not allowed in this task:

- converting Corpus planning context into the canonical schema authority
- adding product-specific behavior to RouteDeck core or React
- broad UI refactors
- query optimization work

- [ ] **Step 3: Run frontend type-check if compatibility edits touch frontend**

Run:

```powershell
cd frontend
npm run type-check
```

Expected: type-check passes.

## Task 11: Full Verification And Closeout

**Files:**

- Modify context/closeout files only when implementation is complete.

- [ ] **Step 1: Run RouteDeck root tests**

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests -q
```

- [ ] **Step 2: Run React tests**

```powershell
cd react
npm test
```

- [ ] **Step 3: Run Medusa backend tests**

```powershell
cd ..\examples\medusa-agent\backend
python -m pytest tests -q
```

- [ ] **Step 4: Run Medusa frontend tests**

```powershell
cd ..\frontend
npm test
```

- [ ] **Step 5: Run doc coverage**

```powershell
cd ..\..\..
python scripts/check_doc_coverage.py
```

- [ ] **Step 6: Run drift scans**

```powershell
rg -n "api/routedeck/(medusa|propertydesk|corpus|saastoagent|checkout|cart|order|payment|shipping|fulfillment)|phrase_router|alias_router|command_router|intent_map" examples/medusa-agent routedeck_core react/src
rg -n "Medusa|medusa|cart|checkout|product_ref|variant_ref" routedeck_core react/src
```

Expected: no product-specific framework hits and no phrase-router hits.

- [ ] **Step 7: Manual smoke with Medusa unavailable**

Start backend and frontend. Confirm:

- setup shows local demo Medusa unavailable
- `GET /api/routedeck/projection` returns no legal commerce operations
- shopper chat does not invent products
- public UI does not show RouteDeck internals

- [ ] **Step 8: Manual smoke with local/demo Medusa available**

Start local/demo Medusa with `MEDUSA_BACKEND_URL` and `MEDUSA_PUBLISHABLE_API_KEY`. Confirm:

- product list projection includes capabilities, available entities, and surface affordances
- UI opens product detail through a surface event
- UI selects a variant through a surface event
- UI adds selected item through a surface event
- chat can browse products and add a selected variant through planning-context entity binding
- no private Medusa IDs appear in public transcript or visible UI
- no checkout/payment/shipping/admin UI appears in this readiness track

- [ ] **Step 9: Closeout**

Follow `work_prompt.md` session-end rules:

- create a log entry in `logs/`
- create a checkpoint in `context_checkpoints/`
- archive and rewrite `context.md` if materially changed
- name changed files and owning `architecture/code-map.md` subsystem rows
- update related docs/test index/architecture docs
- run `python scripts/check_doc_coverage.py`
- run fastest meaningful validation command for changed areas

## Self-Review

Spec coverage:

- Core schemas/models: covered in Tasks 1 and 2.
- React RouteDeckStore/types/hooks: covered in Task 3.
- Medusa planning context, navgraph, capabilities, surface affordances, hidden route operations: covered in Tasks 4 through 8.
- Docs/tests: covered in Tasks 8, 9, and 11.
- SaaStoAgent Corpus agent: covered as a compatibility gate in Task 10, intentionally not the schema driver.

Boundary coverage:

- Product/framework boundary is explicit in every phase.
- RouteDeck remains product-neutral.
- Medusa owns prompts, planning context, domain API calls, side effects, UI copy, and product agent execution.
- `/api/routedeck/*` remains generic and domain child paths under that API plane are banned.
- Anything surface-doable is required to be chat-doable through planning context.
- Hidden `route.*` operations remain runtime plumbing.

Hardcoding coverage:

- Runtime product data comes from the Medusa Store API or tests.
- Entity binding uses current available entities and opaque refs.
- No phrase router, alias router, command router, or fake catalog path is allowed.
- Guard scans and tests explicitly protect against those regressions.
