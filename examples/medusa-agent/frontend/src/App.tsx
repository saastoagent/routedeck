import { FormEvent, useEffect, useRef, useState } from "react";

import type {
  ProductSummary,
  RouteDeckAvailableEntity,
  RouteDeckCapability,
  RouteDeckEvent,
  RouteDeckNavGraph,
  RouteDeckOperation,
  RouteDeckProjection,
  RouteDeckSurfaceAffordance,
  RouteDeckSurfaceEvent,
} from "./hooks/useRouteDeckProjection";
import { useRouteDeckProjection } from "./hooks/useRouteDeckProjection";
import { THINKING_PLACEHOLDER, useSSEChat } from "./hooks/useSSEChat";

export default function App() {
  const [draft, setDraft] = useState("");
  const { projection, error, dispatchSurfaceEvent, dispatchOperation, applyRouteDeckEvent, sessionId } = useRouteDeckProjection();
  const { messages, isStreaming, sendMessage } = useSSEChat({
    onRouteDeckEvent: (event) => applyRouteDeckEvent(event as RouteDeckEvent),
    sessionId,
  });
  const setupReady = projection?.surfaces?.active?.props?.setup?.ready === true;
  const setupLabel = setupReady ? "Connected" : "Needs local demo Medusa";
  const activeSurface = projection?.surfaces?.active;
  const chatActions = actionChipsForProjection(projection);
  const latestAssistantMessageId = latestCompletedAssistantMessageId(messages);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const next = draft.trim();
    if (!next) return;
    sendMessage(next);
    setDraft("");
  };

  return (
    <main className="app-shell">
      <section className="chat-shell" aria-label="Medusa commerce chat">
        <header className="chat-header">
          <div>
            <h1>Medusa Agent</h1>
            <p>Commerce chat for demo shopping questions.</p>
          </div>
          <span className={isStreaming ? "status status-live" : "status"} aria-live="polite">
            {isStreaming ? "Streaming" : "Ready"}
          </span>
        </header>

        <section className="setup-status" aria-label="Setup readiness">
          <span className="setup-label">Setup</span>
          <span className={setupReady ? "setup-value setup-connected" : "setup-value"}>
            {error ? "Needs local demo Medusa" : setupLabel}
          </span>
        </section>

        <div className="agent-workspace" data-testid="medusa-agent-workspace">
          <div className="messages" aria-live="polite" data-testid="medusa-chat-stream">
            {messages.length === 0 ? (
              <div className="message-row assistant starter-message" data-testid="medusa-starter-message">
                <div className="message-bubble">
                  Ask about products, styles, sizing, or what to look at first.
                </div>
                <ActionChips
                  actions={chatActions}
                  className="chat-action-chips starter-chat-actions"
                  dispatchOperation={dispatchOperation}
                />
              </div>
            ) : (
              messages.map((message) => (
                <div className={`message-row ${message.role}`} key={message.id}>
                  <div className="message-bubble">
                    {message.isStreaming && message.content === THINKING_PLACEHOLDER ? (
                      <ThinkingMessage />
                    ) : (
                      message.content || (message.isStreaming ? "..." : "")
                    )}
                  </div>
                  {message.id === latestAssistantMessageId ? (
                    <ActionChips
                      actions={chatActions}
                      className="chat-action-chips"
                      dispatchOperation={dispatchOperation}
                    />
                  ) : null}
                </div>
              ))
            )}
            <CommerceSurface
              surface={activeSurface}
              dispatchSurfaceEvent={dispatchSurfaceEvent}
            />
          </div>

          <AgentContextPanel projection={projection} />
        </div>

        <form className="composer" onSubmit={submit}>
          <label className="sr-only" htmlFor="message">
            Message
          </label>
          <input
            id="message"
            aria-label="Message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask for shopping help"
            disabled={isStreaming}
          />
          <button type="submit" disabled={isStreaming || !draft.trim()}>
            Send
          </button>
        </form>
      </section>
    </main>
  );
}

function ThinkingMessage() {
  const steps = ["Checking context", "Reviewing options", "Preparing reply"];

  return (
    <div className="thinking-state" aria-label="Assistant is preparing a response">
      <div className="thinking-title">
        <span>Thinking</span>
        <span className="thinking-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
      </div>
      <ol className="thinking-steps">
        {steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </div>
  );
}

function actionChipsForProjection(projection?: RouteDeckProjection | null) {
  const currentNode = projection?.graph_node ?? projection?.navgraph?.current?.node_id ?? projection?.navigation?.current?.node_id;
  return (projection?.legal_operations ?? [])
    .filter((operation) => !operation.id.startsWith("route.") && operation.invocation_kind !== "hidden")
    .filter((operation) => operation.execution_mode !== "blocked")
    .filter((operation) => operation.can_dispatch_now !== false)
    .filter((operation) => !(operation.missing_args ?? []).length)
    .filter((operation) => {
      const invocation = operation.invocation_kind ?? (operation.kind === "form" ? "form" : "direct");
      return invocation === "direct" || invocation === "surface";
    })
    .filter((operation) => !(currentNode && operation.target_node === currentNode))
    .slice(0, 4);
}

function latestCompletedAssistantMessageId(messages: Array<{ id: string; role: string; isStreaming?: boolean }>) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.role === "assistant" && !message.isStreaming) {
      return message.id;
    }
  }
  return null;
}

function ActionChips({
  actions,
  className = "",
  dispatchOperation,
}: {
  actions: RouteDeckOperation[];
  className?: string;
  dispatchOperation: (operationId: string) => Promise<void>;
}) {
  if (!actions.length) return null;

  return (
    <section className={`action-chip-panel ${className}`} aria-label="Suggested chat actions" data-testid="medusa-chat-action-chips">
      <div className="action-chip-row">
        {actions.map((operation) => (
          <button
            className="action-chip"
            key={operation.id}
            onClick={() => void dispatchOperation(operation.id)}
            title={operation.description || operation.label}
            type="button"
          >
            {actionLabel(operation)}
          </button>
        ))}
      </div>
    </section>
  );
}

function CommerceSurface({
  surface,
  dispatchSurfaceEvent,
}: {
  surface: NonNullable<NonNullable<RouteDeckProjection["surfaces"]>["active"]> | undefined;
  dispatchSurfaceEvent: (surfaceEvent: RouteDeckSurfaceEvent) => Promise<void>;
}) {
  if (!surface || surface.variant === "setup_status") {
    return (
      <section className="shopping-surface" aria-label="Shopping surface" data-testid="medusa-shopping-surface">
        <div className="surface-empty">
          <span>Waiting for commerce state</span>
        </div>
      </section>
    );
  }
  const props = surface.props ?? {};
  const surfaceId = surface.surface_id;
  const emitSurfaceEvent = (affordanceId: string, entityKey?: string | null, payload?: Record<string, unknown>) => {
    if (!surfaceId) return;
    void dispatchSurfaceEvent({
      surface_id: surfaceId,
      affordance_id: affordanceId,
      entity_key: entityKey,
      payload,
    });
  };

  if (surface.variant === "agent_home") {
    return (
      <section className="shopping-surface" aria-label="Shopping surface" data-testid="medusa-shopping-surface">
        <section className="home-context" aria-label="Shopping start">
          <div className="context-heading">
            <span>Start here</span>
          </div>
          <p>{props.summary || "Ask the agent for shopping help or choose an available action."}</p>
          <div className="surface-action-row">
            <button onClick={() => emitSurfaceEvent("browse_products")} type="button">
              Browse products
            </button>
            <button onClick={() => emitSurfaceEvent("view_cart")} type="button">
              View cart
            </button>
          </div>
        </section>
      </section>
    );
  }

  if (surface.variant === "product_list") {
    const products = props.products ?? [];
    return (
      <section className="shopping-surface" aria-label="Shopping surface" data-testid="medusa-shopping-surface">
        <div className="context-heading">
          <span>Available now</span>
        </div>
        {products.length ? (
          <div className="product-grid">
            {products.map((product) => (
              <ProductCard
                key={product.entity_key}
                product={product}
                onView={() => emitSurfaceEvent("view_product", product.entity_key)}
              />
            ))}
          </div>
        ) : (
          <div className="surface-empty">
            <span>No products available</span>
          </div>
        )}
      </section>
    );
  }

  if (surface.variant === "product_detail" && props.product) {
    const product = props.product;
    const selected = props.selected_variant_entity_key;
    return (
      <section className="shopping-surface" aria-label="Shopping surface" data-testid="medusa-shopping-surface">
        <div className="context-heading">
          <span>Current product</span>
        </div>
        <div className="product-detail">
          <ProductMedia product={product} />
          <div className="product-copy">
            <h2>{product.title}</h2>
            {product.description ? <p>{product.description}</p> : null}
            <div className="variant-row" aria-label="Variants">
              {(product.variants ?? []).map((variant) => (
                <button
                  className={selected === variant.entity_key ? "variant-button selected" : "variant-button"}
                  key={variant.entity_key}
                  onClick={() => emitSurfaceEvent("select_variant", variant.entity_key)}
                  type="button"
                >
                  {variant.title}
                </button>
              ))}
            </div>
            <button
              className="commerce-action"
              disabled={!selected}
              onClick={() => selected && emitSurfaceEvent("add_variant_to_cart", selected, { quantity: 1 })}
              type="button"
            >
              Add selected item
            </button>
          </div>
        </div>
      </section>
    );
  }

  if (surface.variant === "cart_summary") {
    const items = props.cart?.items ?? [];
    return (
      <section className="shopping-surface" aria-label="Shopping surface" data-testid="medusa-shopping-surface">
        <div className="cart-summary">
          <h2>Cart</h2>
          {items.length ? (
            <ul>
              {items.map((item) => (
                <li key={item.entity_key ?? `${item.title}-${item.quantity}`}>
                  <span>{item.title || "Selected item"}</span>
                  <strong>{item.quantity}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p>No items selected yet.</p>
          )}
        </div>
      </section>
    );
  }

  return (
    <section className="shopping-surface" aria-label="Shopping surface" data-testid="medusa-shopping-surface">
      <div className="surface-empty">
        <span>No active commerce surface</span>
      </div>
    </section>
  );
}

function AgentContextPanel({ projection }: { projection?: RouteDeckProjection | null }) {
  const navgraph = projection?.navgraph;
  if (!projection && !navgraph) return null;

  return (
    <aside className="agent-context-panel" aria-label="Agent context" data-testid="medusa-agent-context">
      <NavGraphView navgraph={navgraph} projection={projection} />
    </aside>
  );
}

function NavGraphView({
  navgraph,
  projection,
}: {
  navgraph?: RouteDeckNavGraph | null;
  projection?: RouteDeckProjection | null;
}) {
  const nodes = navgraph?.nodes ?? [];
  if (!nodes.length) return null;

  const currentNodeId = navgraph?.current?.node_id;
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const previousCurrentNodeId = useRef(currentNodeId);
  useEffect(() => {
    if (previousCurrentNodeId.current !== currentNodeId) {
      previousCurrentNodeId.current = currentNodeId;
      setSelectedNodeId(null);
    }
  }, [currentNodeId]);
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? nodes.find((node) => node.id === currentNodeId) ?? nodes[0];
  const reachable = new Set(navgraph?.reachable ?? []);
  const labelById = new Map(nodes.map((node) => [node.id, node.label]));
  const nodePositions = layoutNavGraphNodes(nodes);
  const visibleEdges = (navgraph?.edges ?? []).reduce<NonNullable<RouteDeckNavGraph["edges"]>>((uniqueEdges, edge) => {
    const source = edge.from ?? "";
    const target = edge.to ?? "";
    if (!labelById.has(source) || !labelById.has(target)) return uniqueEdges;
    if (uniqueEdges.some((existing) => existing.from === source && existing.to === target)) return uniqueEdges;
    return [...uniqueEdges, edge];
  }, []);

  return (
    <section className="navgraph-panel" aria-label="Agent route map">
      <div className="context-heading">
        <span>Agent route map</span>
      </div>
      <div className="navgraph-canvas">
        <svg aria-label="RouteDeck navigation graph" role="img" viewBox="0 0 260 170">
          <defs>
            <marker id="navgraph-arrow" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
              <path d="M0,0 L8,4 L0,8 Z" />
            </marker>
          </defs>
          {visibleEdges.map((edge) => {
            const source = nodePositions.get(edge.from ?? "");
            const target = nodePositions.get(edge.to ?? "");
            if (!source || !target) return null;
            return (
              <path
                className="navgraph-edge-line"
                d={`M ${source.x} ${source.y} L ${target.x} ${target.y}`}
                key={`${edge.from}-${edge.to}`}
              />
            );
          })}
          {nodes.map((node) => {
            const position = nodePositions.get(node.id);
            if (!position) return null;
            const isCurrent = node.id === currentNodeId;
            const isSelected = node.id === selectedNode.id;
            const isReachable = !isCurrent && reachable.has(node.id);
            const className = `navgraph-node ${isCurrent ? "current" : ""} ${isReachable ? "reachable" : ""} ${isSelected ? "selected" : ""}`;
            const label = `${node.label}${isCurrent ? ", current" : isReachable ? ", reachable" : ""}${isSelected ? ", selected" : ""}`;
            return (
              <g
                aria-label={`Inspect ${label}`}
                className={className}
                key={node.id}
                onClick={() => setSelectedNodeId(node.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedNodeId(node.id);
                  }
                }}
                role="button"
                tabIndex={0}
              >
                <rect height="44" rx="8" width="86" x={position.x - 43} y={position.y - 22} />
                <text x={position.x} y={position.y - 2}>{node.label}</text>
                <text className="navgraph-node-status" x={position.x} y={position.y + 13}>
                  {isCurrent ? "Current" : isReachable ? "Reachable" : isSelected ? "Selected" : ""}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <NavGraphInspector navgraph={navgraph} projection={projection} selectedNodeId={selectedNode.id} />
      <ul className="sr-only">
        {nodes.map((node) => (
          <li key={node.id}>
            {node.label}
            {node.id === currentNodeId ? " current" : reachable.has(node.id) ? " reachable" : ""}
            {node.deeplink?.url ? ` ${node.deeplink.url}` : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}

function layoutNavGraphNodes(nodes: NonNullable<RouteDeckNavGraph["nodes"]>) {
  const preferred: Record<string, { x: number; y: number }> = {
    home: { x: 130, y: 84 },
    browse: { x: 130, y: 30 },
    detail: { x: 58, y: 142 },
    cart: { x: 202, y: 142 },
  };
  const positions = new Map<string, { x: number; y: number }>();
  const fallbackRadius = 58;
  nodes.forEach((node, index) => {
    if (preferred[node.id]) {
      positions.set(node.id, preferred[node.id]);
      return;
    }
    const angle = -Math.PI / 2 + (index / Math.max(nodes.length, 1)) * Math.PI * 2;
    positions.set(node.id, {
      x: 130 + Math.cos(angle) * fallbackRadius,
      y: 86 + Math.sin(angle) * fallbackRadius,
    });
  });
  return positions;
}

function NavGraphInspector({
  navgraph,
  projection,
  selectedNodeId,
}: {
  navgraph: RouteDeckNavGraph;
  projection?: RouteDeckProjection | null;
  selectedNodeId: string;
}) {
  const nodes = navgraph.nodes ?? [];
  const node = nodes.find((candidate) => candidate.id === selectedNodeId);
  if (!node) return null;

  const capabilityLabels = capabilityLabelsForNode(node.capability_ids ?? [], projection?.capabilities ?? []);
  const actionLabels = actionLabelsForNode(node, projection?.legal_operations ?? []);
  const entityLabels = entityLabelsForNode(node, projection?.available_entities ?? []);
  const affordanceLabels = affordanceLabelsForNode(node, projection?.surface_affordances ?? []);
  const edgeLabels = edgeLabelsForNode(node.id, navgraph, projection?.legal_operations ?? [], nodes);

  return (
    <section className="navgraph-inspector" aria-label="Route inspector">
      <div className="inspector-header">
        <span>{node.label}</span>
        <small>{node.id === navgraph.current?.node_id ? "Current" : (navgraph.reachable ?? []).includes(node.id) ? "Reachable" : "Inspecting"}</small>
      </div>
      {node.metadata?.description ? <p>{node.metadata.description}</p> : null}
      <InspectorList title="Capabilities" values={capabilityLabels} empty="No active capability." />
      <InspectorList title="Actions" values={actionLabels} empty="No ready action here." />
      <InspectorList title="Entities" values={entityLabels} empty="No rendered entities." />
      <InspectorList title="Affordances" values={affordanceLabels} empty="No surface affordance." />
      <InspectorList title="Routes" values={edgeLabels} empty="No outgoing route." />
      {node.deeplink?.url ? (
        <div className="inspector-deeplink">
          <span>Address</span>
          <code>{node.deeplink.url}</code>
        </div>
      ) : null}
    </section>
  );
}

function InspectorList({ title, values, empty }: { title: string; values: string[]; empty: string }) {
  const uniqueValues = Array.from(new Set(values.filter(Boolean)));
  return (
    <div className="inspector-group">
      <span>{title}</span>
      {uniqueValues.length ? (
        <ul>
          {uniqueValues.map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      ) : (
        <p>{empty}</p>
      )}
    </div>
  );
}

function capabilityLabelsForNode(capabilityIds: string[], capabilities: RouteDeckCapability[]) {
  const labelsById = new Map(capabilities.map((capability) => [capability.capability_id, capability.label]));
  return capabilityIds.map((capabilityId) => labelsById.get(capabilityId) ?? readableToken(capabilityId));
}

function actionLabelsForNode(node: NonNullable<RouteDeckNavGraph["nodes"]>[number], operations: RouteDeckOperation[]) {
  const allowed = new Set(node.metadata?.allowed_actions ?? []);
  return operations
    .filter((operation) => !operation.id.startsWith("route.") && operation.invocation_kind !== "hidden")
    .filter((operation) => !allowed.size || allowed.has(operation.id))
    .map(actionLabel);
}

function entityLabelsForNode(node: NonNullable<RouteDeckNavGraph["nodes"]>[number], entities: RouteDeckAvailableEntity[]) {
  return entities
    .filter((entity) => !node.surface_id || (entity.rendered_on ?? []).includes(node.surface_id))
    .map((entity) => entity.parent_label ? `${entity.parent_label}: ${entity.label}` : entity.label);
}

function affordanceLabelsForNode(node: NonNullable<RouteDeckNavGraph["nodes"]>[number], affordances: RouteDeckSurfaceAffordance[]) {
  return affordances
    .filter((affordance) => !node.surface_id || affordance.surface_id === node.surface_id)
    .map((affordance) => affordanceLabel(affordance));
}

function edgeLabelsForNode(
  nodeId: string,
  navgraph: RouteDeckNavGraph,
  operations: RouteDeckOperation[],
  nodes: NonNullable<RouteDeckNavGraph["nodes"]>,
) {
  const operationLabels = new Map(operations.map((operation) => [operation.id, actionLabel(operation)]));
  const nodeLabels = new Map(nodes.map((node) => [node.id, node.label]));
  return (navgraph.edges ?? [])
    .filter((edge) => edge.from === nodeId)
    .map((edge) => {
      const target = nodeLabels.get(edge.to ?? "") ?? "Next location";
      const action = edge.action_id ? operationLabels.get(edge.action_id) ?? actionLabel({ id: edge.action_id, label: readableToken(edge.action_id) }) : null;
      return action ? `${action} -> ${target}` : target;
    });
}

function actionLabel(operation: Pick<RouteDeckOperation, "id" | "label">) {
  const labels: Record<string, string> = {
    "catalog.list": "Browse products",
    "catalog.open": "View product",
    "variant.select": "Choose variant",
    "cart.create": "Start cart",
    "cart.add_item": "Add to cart",
    "cart.view": "View cart",
  };
  return labels[operation.id] ?? operation.label ?? readableToken(operation.id);
}

function affordanceLabel(affordance: RouteDeckSurfaceAffordance) {
  const labels: Record<string, string> = {
    view_product: "Open product from surface",
    select_variant: "Choose rendered variant",
    add_variant_to_cart: "Add selected variant",
  };
  return labels[affordance.affordance_id] ?? readableToken(affordance.affordance_id);
}

function readableToken(value: string) {
  return value
    .replace(/^route\./, "")
    .replace(/[._-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function ProductCard({ product, onView }: { product: ProductSummary; onView: () => void }) {
  return (
    <article className="product-card">
      <ProductMedia product={product} />
      <div className="product-card-body">
        <h2>{product.title}</h2>
        {product.description ? <p>{product.description}</p> : null}
        {product.variants?.length ? (
          <div className="variant-preview">
            {product.variants.slice(0, 3).map((variant) => (
              <span key={variant.entity_key}>{variant.title}</span>
            ))}
          </div>
        ) : null}
        <button aria-label={`View ${product.title}`} onClick={onView} type="button">
          View
        </button>
      </div>
    </article>
  );
}

function ProductMedia({ product }: { product: ProductSummary }) {
  return product.thumbnail ? (
    <img alt="" className="product-media" src={product.thumbnail} />
  ) : (
    <div className="product-media product-media-empty" aria-hidden="true" />
  );
}
