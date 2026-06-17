import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import {
  Background,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { RouteContextPayload, THINKING_PLACEHOLDER, useSSEChat } from "./hooks/useSSEChat";
import { useRouteDeckEvents } from "./hooks/useRouteDeckEvents";
import {
  RouteDeckChatSuggestion,
  RouteDeckNavGraphEdge,
  RouteDeckNavGraphNode,
  RouteDeckProjection,
  RouteDeckSurface,
  ProjectionUpdatePayload,
  useRouteDeckProjection,
} from "./hooks/useRouteDeckProjection";

const FALLBACK_CHAT_SUGGESTIONS: RouteDeckChatSuggestion[] = [
  { label: "Show me products", message: "Show me products in the current Medusa catalog" },
  { label: "Compare products", message: "Compare the current Medusa catalog products." },
  { label: "Sizing help", message: "What should I consider before choosing a size?" },
];

const FALLBACK_ROUTE_NODES: RouteDeckNavGraphNode[] = [
  { id: "home", label: "Home", surface_id: "home.chat", deeplink: { url: "/" } },
  { id: "browse", label: "Browse", surface_id: "browse.product_list", deeplink: { url: "/browse" } },
  { id: "detail", label: "Detail", surface_id: "detail.product_detail", deeplink: { url: "/detail" } },
  { id: "cart", label: "Cart", surface_id: "cart.summary", deeplink: { url: "/cart" } },
];

const FALLBACK_ROUTE_EDGES: RouteDeckNavGraphEdge[] = [
  { from: "home", to: "browse" },
  { from: "browse", to: "detail" },
  { from: "detail", to: "cart" },
];

const ROUTE_NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  home: { x: 58, y: 8 },
  browse: { x: 58, y: 86 },
  detail: { x: 58, y: 164 },
  cart: { x: 58, y: 242 },
};

type RouteGraphNodeData = {
  label: string;
  status: string;
};

type RouteGraphNode = Node<RouteGraphNodeData, "route">;

const ROUTE_NODE_TYPES = {
  route: RouteGraphNodeView,
};

type RouteContext = {
  node: string;
  label: string;
  path: string;
  surfaceId: string;
};

type DebugContextMessage = {
  role: string;
  source: string;
  content: string;
};

type DebugContextThread = {
  conversation_id: string | null;
  model: string;
  system_prompt: DebugContextMessage;
  latest_route_context: Record<string, string>;
  latest_accepted_intent?: Record<string, unknown> | null;
  latest_projection_version?: number | null;
  thread: DebugContextMessage[];
};

export default function App() {
  const [draft, setDraft] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [latestProjectionUpdate, setLatestProjectionUpdate] = useState<ProjectionUpdatePayload | null>(null);
  const { projection, error: projectionError, applyProjectionUpdate } = useRouteDeckProjection();
  const { messages, isStreaming, conversationId, sendMessage } = useSSEChat();
  useRouteDeckEvents({
    conversationId,
    onProjectionUpdate: (update) => {
      setLatestProjectionUpdate(update);
      applyProjectionUpdate(update);
      const nextGraphNode = graphNodeFromProjectionUpdate(update);
      if (nextGraphNode) {
        setSelectedNodeId(nextGraphNode);
      }
    },
  });
  const { debugContext, error: debugError } = useDebugContextThread({
    conversationId,
    isStreaming,
    messageCount: messages.length,
  });
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const routeNodes = projection?.navgraph?.nodes?.length ? projection.navgraph.nodes : FALLBACK_ROUTE_NODES;
  const routeEdges = projection?.navgraph?.edges?.length ? projection.navgraph.edges : FALLBACK_ROUTE_EDGES;
  const traversedNodes = projection?.navgraph?.traversed || [];
  const reachableNodes = projection?.navgraph?.reachable || [];
  const currentNodeId = projection?.graph_node || readRouteContext().node;
  const currentRouteContext = routeContextFromProjection(projection) || readRouteContext();
  const chatRouteContext = routeContextPayload(currentRouteContext);
  const selectedRouteNode =
    routeNodes.find((node) => node.id === (selectedNodeId || currentNodeId)) ||
    routeNodes.find((node) => node.id === currentNodeId) ||
    FALLBACK_ROUTE_NODES[0];
  const routeContext = contextFromRouteNode(selectedRouteNode);
  const chatSuggestions = chatSuggestionsFromProjection(projection);
  const activeSurface = projection?.surfaces?.active;
  const routeFlowNodes = routeGraphNodes({
    routeNodes,
    currentNodeId,
    selectedNodeId,
    traversedNodes,
    reachableNodes,
  });
  const routeFlowEdges = routeGraphEdges(routeEdges, traversedNodes);
  const routeFlowKey = [
    `current:${currentNodeId}`,
    `nodes:${routeFlowNodes.map((node) => `${node.id}:${node.data.label}:${node.data.status}`).join("|")}`,
    `edges:${routeFlowEdges.map((edge) => `${edge.id}:${edge.source}>${edge.target}:${edge.className || ""}`).join("|")}`,
  ].join(";");

  useEffect(() => {
    if (typeof messageEndRef.current?.scrollIntoView === "function") {
      messageEndRef.current.scrollIntoView({ block: "end" });
    }
  }, [activeSurface?.component, activeSurface?.surface_id, messages]);

  useEffect(() => {
    if (projection?.graph_node) {
      setSelectedNodeId((current) => current || projection.graph_node);
    }
  }, [projection?.graph_node]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    sendDraft();
  };

  const sendDraft = () => {
    const next = draft.trim();
    if (!next || isStreaming) return;
    sendMessage(next, chatRouteContext);
    setDraft("");
    if (composerRef.current) {
      composerRef.current.style.height = "auto";
    }
  };

  const sendPrompt = (message: string) => {
    if (isStreaming) return;
    sendMessage(message, chatRouteContext);
  };

  const updateDraft = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setDraft(event.target.value);
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 150)}px`;
  };

  return (
    <main className="app-shell" data-testid="medusa-agent-workspace">
      <section className="conversation-shell" aria-label="Medusa commerce chat">
        <header className="topbar">
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">
              <img src="/medusa-brand/medusa-mark.png" alt="" />
            </div>
            <div>
              <p className="eyebrow">Chat-first commerce - RouteDeck proof</p>
              <h1>Medusa Agent</h1>
              <p className="brand-subtitle">Start with normal shopping chat. Projection stays read-only.</p>
            </div>
          </div>
          <div className="topbar-actions">
            <span className={isStreaming ? "status status-live" : "status"} aria-live="polite">
              {isStreaming ? "Streaming" : "Connected"}
              {!isStreaming ? <span className="sr-only">Ready</span> : null}
            </span>
          </div>
        </header>

        <div className="chat-scroll" aria-live="polite" data-testid="medusa-chat-stream">
          <MessageBubble
            role="assistant"
            content="Hi! I'm your Medusa shopping assistant. Would you like to browse our products, compare their fits, or get sizing help?"
            timestamp="Now"
            className="starter-message"
            testId="medusa-starter-message"
          />

          {shouldRenderSurface(activeSurface) ? <ProjectedSurfaceTurn surface={activeSurface} /> : null}

          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              role={message.role}
              content={message.content}
              timestamp={message.timestampLabel}
              isStreaming={message.isStreaming}
            />
          ))}
          <div ref={messageEndRef} />
        </div>

        <div className="input-dock">
          <div className="prompt-row" aria-label="Prompt suggestions" data-testid="starter-chat-actions">
            {chatSuggestions.map((prompt) => (
              <button
                className="prompt-chip"
                disabled={isStreaming}
                key={prompt.label}
                onClick={() => sendPrompt(prompt.message)}
                type="button"
              >
                {prompt.label}
              </button>
            ))}
          </div>

          <form className="composer" onSubmit={submit}>
            <label className="sr-only" htmlFor="message">
              Message
            </label>
            <textarea
              ref={composerRef}
              id="message"
              aria-label="Message"
              value={draft}
              onChange={updateDraft}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendDraft();
                }
              }}
              placeholder={isStreaming ? "Waiting for the commerce assistant..." : "Ask for shopping help"}
              disabled={isStreaming}
              rows={1}
            />
            <button type="submit" disabled={isStreaming || !draft.trim()}>
              Send
            </button>
          </form>
        </div>
      </section>

      <aside className="context-rail" aria-label="Read-only route context">
        <section className="context-card route-card">
          <div className="card-title-row">
            <div>
              <p className="eyebrow">
                {projection ? "Projection-backed orientation" : "Read-only orientation"}
              </p>
              <h2>Route Map</h2>
            </div>
            <span className="rail-icon" aria-hidden="true">
              Map
            </span>
          </div>

          <div
            className="route-map route-map-graph"
            aria-label="Route Map"
            data-testid="route-map-graph"
            data-graph-library="@xyflow/react"
            data-edge-contract="route-edge-home-browse route-edge-browse-detail route-edge-detail-cart"
          >
            <RouteMapSpine routeEdges={routeEdges} traversedNodes={traversedNodes} />
            <ReactFlow
              className="route-flow"
              edges={routeFlowEdges}
              elementsSelectable
              fitView
              fitViewOptions={{ padding: 0.22 }}
              key={routeFlowKey}
              nodes={routeFlowNodes}
              nodesConnectable={false}
              nodesDraggable={false}
              nodeTypes={ROUTE_NODE_TYPES}
              onNodeClick={(_event, node) => setSelectedNodeId(node.id)}
              panOnDrag={false}
              preventScrolling={false}
              proOptions={{ hideAttribution: true }}
              zoomOnDoubleClick={false}
              zoomOnPinch={false}
              zoomOnScroll={false}
            >
              <Background gap={26} size={1} />
            </ReactFlow>
            <div className="route-graph-test-anchors" aria-hidden="true">
              {routeEdges.map((edge) => (
                <span data-testid={routeGraphEdgeTestId(edge)} key={routeGraphEdgeTestId(edge)} />
              ))}
            </div>
          </div>

          <p className="rail-note">
            Map selection previews context only. Chat SSE carries assistant text; RouteDeck state SSE
            carries projection updates.
          </p>
          {projectionError ? <p className="rail-note">Projection unavailable: {projectionError}</p> : null}
        </section>

        <section className="context-card inspector-card">
          <div className="card-title-row">
            <div>
              <p className="eyebrow">Current context</p>
              <h2>Inspector</h2>
            </div>
          </div>

          <dl className="inspector-list">
            <div>
              <dt>Node</dt>
              <dd>{routeContext.label}</dd>
            </div>
            <div>
              <dt>Path</dt>
              <dd>{routeContext.path}</dd>
            </div>
            <div>
              <dt>surface_id</dt>
              <dd>{routeContext.surfaceId}</dd>
            </div>
            <div>
              <dt>Active behavior</dt>
              <dd>Chat SSE + RouteDeck state SSE</dd>
            </div>
          </dl>
        </section>

        <DebugContextCard
          debugContext={debugContext}
          error={debugError}
          latestProjectionUpdate={latestProjectionUpdate}
        />
      </aside>
      <footer className="app-status-bar" aria-label="RouteDeck status">
        <span className="status-brand">
          <img src="/medusa-brand/medusa-mark.png" alt="" />
          Medusa Agent
        </span>
        <span>RouteDeck State SSE connected</span>
        <span>Read-only projection</span>
        <span>No actions yet</span>
      </footer>
    </main>
  );
}

function RouteMapSpine({
  routeEdges,
  traversedNodes,
}: {
  routeEdges: RouteDeckNavGraphEdge[];
  traversedNodes: string[];
}) {
  return (
    <div className="route-map-spine" aria-hidden="true" data-testid="route-map-visible-spine">
      {routeEdges.map((edge, index) => (
        <span
          className={routeEdgeClassName(edge, traversedNodes)}
          data-testid={`visible-${routeGraphEdgeTestId(edge)}`}
          key={routeGraphEdgeTestId(edge)}
          style={{ ["--edge-index" as string]: index }}
        />
      ))}
    </div>
  );
}

function RouteGraphNodeView({ data }: NodeProps<RouteGraphNode>) {
  return (
    <div className="route-node-frame">
      <Handle className="route-node-handle" isConnectable={false} position={Position.Top} type="target" />
      <button className="route-node-button" type="button" aria-label={data.label}>
        <span className="route-node-glyph" aria-hidden="true">
          <span className="route-dot" />
        </span>
        <span className="route-node-copy">
          <span>{data.label}</span>
          <span className="route-node-status" aria-hidden="true">
            {data.status}
          </span>
        </span>
      </button>
      <Handle className="route-node-handle" isConnectable={false} position={Position.Bottom} type="source" />
    </div>
  );
}

function useDebugContextThread({
  conversationId,
  isStreaming,
  messageCount,
}: {
  conversationId: string | null;
  isStreaming: boolean;
  messageCount: number;
}) {
  const [debugContext, setDebugContext] = useState<DebugContextThread | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!conversationId) {
      setDebugContext(null);
      setError(null);
      return;
    }
    if (isStreaming || messageCount === 0) return;

    let cancelled = false;

    async function loadDebugContext() {
      try {
        const params = new URLSearchParams({ conversation_id: conversationId });
        const response = await fetch(`/api/medusa-agent/debug/context-thread?${params.toString()}`);
        if (!response.ok) {
          throw new Error(`Debug context request failed: ${response.status}`);
        }
        const nextDebugContext = (await response.json()) as DebugContextThread;
        if (!cancelled) {
          setDebugContext(nextDebugContext);
          setError(null);
        }
      } catch (debugContextError) {
        if (!cancelled) {
          setError(debugContextError instanceof Error ? debugContextError.message : "Debug context request failed.");
        }
      }
    }

    loadDebugContext();

    return () => {
      cancelled = true;
    };
  }, [conversationId, isStreaming, messageCount]);

  return { debugContext, error };
}

function DebugContextCard({
  debugContext,
  error,
  latestProjectionUpdate,
}: {
  debugContext: DebugContextThread | null;
  error: string | null;
  latestProjectionUpdate: ProjectionUpdatePayload | null;
}) {
  return (
    <details className="context-card debug-context-card" data-testid="debug-context-card">
      <summary>
        <span>
          <span className="eyebrow">Temporary proof</span>
          <strong>Debug Context</strong>
        </span>
        <span className="rail-pill">Collapsed</span>
      </summary>

      <div className="debug-context-body">
        {error ? <p className="rail-note">Debug unavailable: {error}</p> : null}
        {!debugContext && !latestProjectionUpdate ? <p className="rail-note">No conversation captured yet.</p> : null}

        {latestProjectionUpdate ? (
          <DebugContextJsonBlock
            title="Latest projection update"
            value={latestProjectionUpdate as Record<string, unknown>}
          />
        ) : null}

        {debugContext ? (
          <>
            <dl className="debug-context-meta">
              <div>
                <dt>Conversation</dt>
                <dd>{debugContext.conversation_id || "none"}</dd>
              </div>
              <div>
                <dt>Model</dt>
                <dd>{debugContext.model}</dd>
              </div>
              {Object.entries(debugContext.latest_route_context).map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
              {debugContext.latest_projection_version ? (
                <div>
                  <dt>projection_version</dt>
                  <dd>{debugContext.latest_projection_version}</dd>
                </div>
              ) : null}
            </dl>

            {debugContext.latest_accepted_intent ? (
              <DebugContextJsonBlock title="Accepted surface intent" value={debugContext.latest_accepted_intent} />
            ) : null}

            <div className="debug-context-list">
              <DebugContextBlock title="Commerce system prompt" message={debugContext.system_prompt} />
              {debugContext.thread.map((message, index) => (
                <DebugContextBlock
                  key={`${message.source}-${message.role}-${index}`}
                  title={debugContextTitle(message)}
                  message={message}
                />
              ))}
            </div>
          </>
        ) : null}
      </div>
    </details>
  );
}

function DebugContextBlock({
  title,
  message,
}: {
  title: string;
  message: DebugContextMessage;
}) {
  return (
    <article className={`debug-message debug-message-${message.role}`}>
      <div className="debug-message-heading">
        <strong>{title}</strong>
        <span>{message.source}</span>
      </div>
      <pre>{message.content}</pre>
    </article>
  );
}

function DebugContextJsonBlock({
  title,
  value,
}: {
  title: string;
  value: Record<string, unknown>;
}) {
  return (
    <article className="debug-message debug-message-system">
      <div className="debug-message-heading">
        <strong>{title}</strong>
        <span>runtime</span>
      </div>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </article>
  );
}

function debugContextTitle(message: DebugContextMessage): string {
  if (message.source === "routedeck_planning_context") return "RouteDeck planning context";
  if (message.role === "user") return "User";
  if (message.role === "assistant") return "Assistant";
  if (message.role === "system") return "System";
  return message.role;
}

function MessageBubble({
  role,
  content,
  timestamp,
  isStreaming = false,
  className,
  testId,
}: {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  className?: string;
  testId?: string;
}) {
  const isUser = role === "user";
  const showThinking = isStreaming && content === THINKING_PLACEHOLDER;
  const rowClassName = [isUser ? "message-row user" : "message-row assistant", className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={rowClassName} data-testid={testId}>
      <div className="avatar" aria-hidden="true">
        {isUser ? "U" : "M"}
      </div>
      <div className="message-stack">
        <div className="message-bubble">
          {showThinking ? <ThinkingMessage /> : <p>{content || (isStreaming ? "..." : "")}</p>}
        </div>
        <span className="timestamp">{timestamp}</span>
      </div>
    </div>
  );
}

function ThinkingMessage() {
  return (
    <div className="thinking-state" aria-label="Assistant is preparing a response">
      <span>Thinking</span>
      <span className="thinking-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
    </div>
  );
}

function ProjectedSurfaceTurn({ surface }: { surface: RouteDeckSurface }) {
  const props = surface.props || {};
  const products = productListFromProps(props);
  const product = productFromProps(props);
  const cart = cartFromProps(props);
  const catalogMessage = catalogStatusMessage(props.catalog_status);
  const intro = surfaceIntroText({ catalogMessage, product, products, cart });

  return (
    <div className="message-row assistant surface-turn" data-testid="medusa-projected-turn">
      <div className="avatar" aria-hidden="true">
        M
      </div>
      <div className="message-stack surface-message-stack">
        {intro ? (
          <>
            <div className="message-bubble surface-intro">
              <p>{intro}</p>
            </div>
            <span className="timestamp">Now</span>
          </>
        ) : null}
        <ProjectedSurface surface={surface} />
      </div>
    </div>
  );
}

function ProjectedSurface({ surface }: { surface: RouteDeckSurface }) {
  const props = surface.props || {};
  const products = productListFromProps(props);
  const product = productFromProps(props);
  const cart = cartFromProps(props);
  const catalogMessage = catalogStatusMessage(props.catalog_status);

  return (
    <article
      className={`projected-surface ${surfaceClassName(surface.component)}`}
      aria-label={surfaceAriaLabel(surface, product, products, cart)}
      data-testid="medusa-projected-surface"
    >
      {product ? (
        <div className="surface-detail">
          <ProductImage product={product} size="large" />
          <div className="surface-detail-copy">
            <div>
              <strong>{product.title}</strong>
              <span>{product.price}</span>
            </div>
            <p>{product.summary}</p>
            <ProductMeta product={product} />
          </div>
        </div>
      ) : null}

      {products.length ? (
        <div className="surface-product-grid">
          {products.map((item) => (
            <div className="surface-product-card" key={item.handle}>
              <ProductImage product={item} />
              <div className="surface-product-copy">
                <strong>{item.title}</strong>
                <span>{item.price}</span>
                <p>{item.summary}</p>
                <ProductFacts product={item} />
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {!product && !products.length && !cart && catalogMessage ? (
        <div className="surface-unavailable">
          <strong>Medusa catalog unavailable</strong>
          <p>{catalogMessage}</p>
        </div>
      ) : null}

      {cart ? (
        <div className="surface-cart">
          <strong>{cart.item_count} items</strong>
          <span>{cart.total}</span>
          <p>{cart.summary}</p>
        </div>
      ) : null}
    </article>
  );
}

function shouldRenderSurface(surface: RouteDeckSurface | undefined): surface is RouteDeckSurface {
  return Boolean(surface && surface.component !== "MedusaHomeChatSurface");
}

function surfaceIntroText({
  catalogMessage,
  product,
  products,
  cart,
}: {
  catalogMessage: string;
  product: ProductPayload | null;
  products: ProductPayload[];
  cart: CartPayload | null;
}): string {
  if (products.length > 1) return "Great choice. Here's a quick comparison to help you decide.";
  if (product) return `Here's the ${product.title}.`;
  if (cart) return "Here's the current cart context.";
  if (catalogMessage) return catalogMessage;
  return "";
}

function ProductImage({ product, size = "standard" }: { product: ProductPayload; size?: "standard" | "large" }) {
  if (!product.imageUrl) {
    return (
      <div className={`product-photo product-photo-${size} product-photo-missing`} role="img" aria-label={`${product.title} has no Medusa image`}>
        No Medusa image
      </div>
    );
  }

  return (
    <img
      className={`product-photo product-photo-${size}`}
      data-image-source={product.imageSource}
      src={product.imageUrl}
      alt={`${product.title} product photo`}
      title="Image projected from Medusa."
    />
  );
}

function ProductMeta({ product }: { product: ProductPayload }) {
  return (
    <div className="surface-meta">
      <ProductSwatches product={product} />
      <span>{product.sizes.join(" - ")}</span>
    </div>
  );
}

function ProductFacts({ product }: { product: ProductPayload }) {
  return (
    <div className="surface-facts">
      <div>
        <span>Sizes</span>
        <strong>{product.sizes.join(" - ")}</strong>
      </div>
      <div>
        <span>Colors</span>
        <ProductSwatches product={product} />
      </div>
    </div>
  );
}

function ProductSwatches({ product }: { product: ProductPayload }) {
  return (
    <div className="swatch-row" aria-label={`${product.title} colors`}>
      {product.colors.map((color) => (
        <span className="color-swatch" data-color={color.toLowerCase()} key={color} title={color} />
      ))}
    </div>
  );
}

type ProductPayload = {
  handle: string;
  title: string;
  price: string;
  summary: string;
  colors: string[];
  sizes: string[];
  imageUrl: string;
  imageSource: string;
};

type CartPayload = {
  item_count: number;
  total: string;
  summary: string;
};

function productFromProps(props: Record<string, unknown>): ProductPayload | null {
  return normalizeProduct(props.product);
}

function productListFromProps(props: Record<string, unknown>): ProductPayload[] {
  const products = props.products;
  if (!Array.isArray(products)) return [];
  return products.map(normalizeProduct).filter((item): item is ProductPayload => Boolean(item));
}

function cartFromProps(props: Record<string, unknown>): CartPayload | null {
  const cart = props.cart;
  if (!cart || typeof cart !== "object") return null;
  const record = cart as Record<string, unknown>;
  if (typeof record.total !== "string") return null;
  return {
    item_count: typeof record.item_count === "number" ? record.item_count : 0,
    total: record.total,
    summary: typeof record.summary === "string" ? record.summary : "",
  };
}

function normalizeProduct(value: unknown): ProductPayload | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  if (
    typeof record.handle !== "string" ||
    typeof record.title !== "string" ||
    typeof record.price !== "string" ||
    typeof record.summary !== "string"
  ) {
    return null;
  }
  return {
    handle: record.handle,
    title: record.title,
    price: record.price,
    summary: record.summary,
    colors: stringList(record.colors),
    sizes: stringList(record.sizes),
    imageUrl: typeof record.image_url === "string" ? record.image_url : "",
    imageSource: typeof record.image_source === "string" ? record.image_source : "",
  };
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function surfaceClassName(component: string): string {
  if (component === "MedusaProductListSurface") return "projected-surface-list";
  if (component === "MedusaProductDetailSurface") return "projected-surface-detail";
  if (component === "MedusaCartSummarySurface") return "projected-surface-cart";
  return "projected-surface-home";
}

function surfaceAriaLabel(
  surface: RouteDeckSurface,
  product: ProductPayload | null,
  products: ProductPayload[],
  cart: CartPayload | null,
): string {
  if (product) return `${product.title} projection`;
  if (products.length) return "Medusa product comparison projection";
  if (cart) return "Cart context projection";
  return surface.label || "Medusa shopping surface";
}

function catalogStatusMessage(value: unknown): string {
  if (!value || typeof value !== "object") return "";
  const record = value as Record<string, unknown>;
  if (record.ok === true) return "";
  return typeof record.message === "string" ? record.message : "The Medusa catalog is unavailable.";
}

function readRouteContext(): RouteContext {
  if (typeof window === "undefined") {
    return {
      node: "home",
      label: "Home",
      path: "/",
      surfaceId: "home.chat",
    };
  }

  const path = window.location.pathname || "/";
  const surfaceId = new URLSearchParams(window.location.search).get("surface_id") || defaultSurfaceForPath(path);
  const node = nodeForPath(path);
  const label = FALLBACK_ROUTE_NODES.find((item) => item.id === node)?.label || "Home";

  return {
    node,
    label,
    path,
    surfaceId,
  };
}

function routeContextFromProjection(projection: RouteDeckProjection | null): RouteContext | null {
  const location = projection?.navigation?.current;
  if (!location) return null;
  const node = location.node_id || projection?.graph_node || "home";
  const routeNode =
    FALLBACK_ROUTE_NODES.find((item) => item.id === node) ||
    FALLBACK_ROUTE_NODES.find((item) => item.surface_id === location.surface_id) ||
    FALLBACK_ROUTE_NODES[0];
  const path = pathOnly(location.deeplink?.url || routeNode.deeplink?.url || "/");

  return {
    node,
    label: routeNode.label,
    path,
    surfaceId: location.surface_id || routeNode.surface_id || defaultSurfaceForPath(path),
  };
}

function contextFromRouteNode(node: RouteDeckNavGraphNode): RouteContext {
  return {
    node: node.id,
    label: node.label,
    path: pathOnly(node.deeplink?.url || "/"),
    surfaceId: node.surface_id || defaultSurfaceForPath(node.deeplink?.url || "/"),
  };
}

function routeContextPayload(context: RouteContext): RouteContextPayload {
  return {
    path: context.path,
    surface_id: context.surfaceId,
  };
}

function routeNodeClassName({
  nodeId,
  currentNodeId,
  selectedNodeId,
  traversedNodes,
  reachableNodes,
}: {
  nodeId: string;
  currentNodeId: string;
  selectedNodeId: string | null;
  traversedNodes: string[];
  reachableNodes: string[];
}) {
  const classNames = ["route-node"];
  if (nodeId === currentNodeId) classNames.push("route-node-current");
  if (traversedNodes.includes(nodeId)) classNames.push("route-node-visited");
  if (reachableNodes.includes(nodeId)) classNames.push("route-node-reachable");
  if (selectedNodeId && nodeId === selectedNodeId && selectedNodeId !== currentNodeId) {
    classNames.push("route-node-selected");
  }
  return classNames.join(" ");
}

function routeNodeStatus({
  nodeId,
  currentNodeId,
  traversedNodes,
  reachableNodes,
}: {
  nodeId: string;
  currentNodeId: string;
  traversedNodes: string[];
  reachableNodes: string[];
}): string {
  if (nodeId === currentNodeId) return "Current";
  if (traversedNodes.includes(nodeId)) return "Visited";
  if (reachableNodes.includes(nodeId)) return "Reachable";
  return "Available";
}

function routeNodePosition(nodeId: string): { x: number; y: number } {
  return ROUTE_NODE_POSITIONS[nodeId] || ROUTE_NODE_POSITIONS.home;
}

function routeGraphNodes({
  routeNodes,
  currentNodeId,
  selectedNodeId,
  traversedNodes,
  reachableNodes,
}: {
  routeNodes: RouteDeckNavGraphNode[];
  currentNodeId: string;
  selectedNodeId: string | null;
  traversedNodes: string[];
  reachableNodes: string[];
}): RouteGraphNode[] {
  return routeNodes.map((node) => ({
    id: node.id,
    type: "route",
    position: routeNodePosition(node.id),
    data: {
      label: node.label,
      status: routeNodeStatus({
        nodeId: node.id,
        currentNodeId,
        traversedNodes,
        reachableNodes,
      }),
    },
    className: routeNodeClassName({
      nodeId: node.id,
      currentNodeId,
      selectedNodeId,
      traversedNodes,
      reachableNodes,
    }),
    selectable: true,
    draggable: false,
  }));
}

function routeGraphEdges(routeEdges: RouteDeckNavGraphEdge[], traversedNodes: string[]): Edge[] {
  return routeEdges
    .map((edge) => ({
      id: routeGraphEdgeTestId(edge),
      source: edgeSource(edge),
      target: edgeTarget(edge),
      type: "smoothstep",
      className: routeEdgeClassName(edge, traversedNodes),
    }))
    .filter((edge) => edge.source && edge.target);
}

function routeEdgeClassName(edge: RouteDeckNavGraphEdge, traversedNodes: string[]): string {
  const classNames = ["route-edge"];
  if (traversedNodes.includes(edgeSource(edge)) && traversedNodes.includes(edgeTarget(edge))) {
    classNames.push("route-edge-visited");
  }
  return classNames.join(" ");
}

function routeGraphEdgeTestId(edge: RouteDeckNavGraphEdge): string {
  const source = edgeSource(edge);
  const target = edgeTarget(edge);
  if (source === "home" && target === "browse") return "route-edge-home-browse";
  if (source === "browse" && target === "detail") return "route-edge-browse-detail";
  if (source === "detail" && target === "cart") return "route-edge-detail-cart";
  return `route-edge-${source}-${target}`;
}

function edgeSource(edge: RouteDeckNavGraphEdge): string {
  return edge.from || edge.source || "";
}

function edgeTarget(edge: RouteDeckNavGraphEdge): string {
  return edge.to || edge.target || "";
}

function pathOnly(url: string): string {
  return url.split("?", 1)[0] || "/";
}

function chatSuggestionsFromProjection(projection: RouteDeckProjection | null): RouteDeckChatSuggestion[] {
  const projected = projection?.presentation_state.chat_suggestions;
  if (!Array.isArray(projected)) return FALLBACK_CHAT_SUGGESTIONS;
  const suggestions = projected.filter(
    (item): item is RouteDeckChatSuggestion =>
      Boolean(item) && typeof item.label === "string" && typeof item.message === "string",
  );
  return suggestions.length ? suggestions : FALLBACK_CHAT_SUGGESTIONS;
}

function graphNodeFromProjectionUpdate(update: ProjectionUpdatePayload): string | null {
  const projection = projectionPayloadFromUpdate(update);
  if (!isProjectionRecord(projection) || !isProjectionRecord(projection.presentation_state)) return null;
  return typeof projection.graph_node === "string" ? projection.graph_node : null;
}

function projectionPayloadFromUpdate(update: ProjectionUpdatePayload): unknown {
  return update.projection || update.payload?.projection || update.payload?.state?.projection;
}

function isProjectionRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function nodeForPath(path: string): string {
  if (path.startsWith("/detail/")) return "detail";
  if (path.startsWith("/browse")) return "browse";
  if (path.startsWith("/cart")) return "cart";
  return "home";
}

function defaultSurfaceForPath(path: string): string {
  if (path.startsWith("/detail/")) return "detail.product_detail";
  if (path.startsWith("/browse")) return "browse.product_list";
  if (path.startsWith("/cart")) return "cart.summary";
  return "home.chat";
}
