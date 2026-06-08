import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";
import { parseSSEFrames } from "./hooks/useSSEChat";

class FakeXMLHttpRequest {
  static instances: FakeXMLHttpRequest[] = [];

  method = "";
  url = "";
  requestBody = "";
  responseText = "";
  headers: Record<string, string> = {};
  onprogress: (() => void) | null = null;
  onloadend: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor() {
    FakeXMLHttpRequest.instances.push(this);
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  send(body: string) {
    this.requestBody = body;
  }

  push(frame: string) {
    this.responseText += frame;
    this.onprogress?.();
  }

  finish() {
    this.onloadend?.();
  }

  abort() {}
}

const product = {
  entity_key: "product:entity_public",
  title: "Medusa T-Shirt",
  thumbnail: "https://example.test/shirt.png",
  variants: [{ entity_key: "variant:entity_public", title: "M" }],
};

const baseNodes = [
  {
    id: "home",
    label: "Home",
    surface_id: "home.agent_start",
    deeplink: { url: "/", resumable: true },
    capability_ids: ["catalog.browse"],
    metadata: { description: "Start the Medusa buyer-agent session.", allowed_actions: ["catalog.list", "cart.view"] },
  },
  {
    id: "browse",
    label: "Browse",
    surface_id: "browse.product_list",
    deeplink: { url: "/browse", resumable: true },
    capability_ids: ["catalog.browse"],
    metadata: { description: "Show local demo Medusa products.", allowed_actions: ["catalog.list", "catalog.open", "cart.view"] },
  },
  {
    id: "detail",
    label: "Product Detail",
    surface_id: "detail.product_detail",
    deeplink: { url: "/detail/medusa-t-shirt", resumable: true },
    capability_ids: ["product.configure"],
    metadata: { description: "Show one product and its variants.", allowed_actions: ["catalog.open", "variant.select", "cart.view"] },
  },
  {
    id: "cart",
    label: "Cart",
    surface_id: "cart.cart_summary",
    deeplink: { url: "/cart", resumable: true },
    capability_ids: ["cart.manage"],
    metadata: { description: "Show selected demo cart items.", allowed_actions: ["cart.create", "cart.add_item", "cart.view"] },
  },
];

const baseEdges = [
  { from: "home", to: "browse", action_id: "catalog.list", capability_id: "catalog.browse" },
  { from: "home", to: "cart", action_id: "cart.view", capability_id: "cart.manage" },
  { from: "browse", to: "detail", action_id: "catalog.open", capability_id: "catalog.browse" },
  { from: "browse", to: "cart", action_id: "cart.view", capability_id: "cart.manage" },
  { from: "detail", to: "cart", action_id: "cart.view", capability_id: "cart.manage" },
  { from: "cart", to: "browse", action_id: "catalog.list", capability_id: "catalog.browse" },
];

const capabilities = [
  { capability_id: "catalog.browse", label: "Browse catalog", operation_ids: ["catalog.list", "catalog.open"] },
  { capability_id: "product.configure", label: "Choose product options", operation_ids: ["variant.select"] },
  { capability_id: "cart.manage", label: "Manage demo cart", operation_ids: ["cart.view", "cart.add_item"] },
];

function navgraph(current: string, surfaceId: string, reachable: string[]) {
  const currentNode = baseNodes.find((node) => node.id === current) ?? baseNodes[0];
  return {
    current: {
      node_id: current,
      surface_id: surfaceId,
      deeplink: currentNode.deeplink,
    },
    nodes: baseNodes,
    edges: baseEdges,
    reachable,
  };
}

function homeProjection() {
  return {
    graph_node: "home",
    legal_operations: [
      { id: "catalog.list", label: "Browse products", can_dispatch_now: true, invocation_kind: "direct", target_node: "browse" },
      { id: "cart.view", label: "View cart", can_dispatch_now: true, invocation_kind: "direct", target_node: "cart" },
      { id: "route.open_node", label: "Open node", can_dispatch_now: true, invocation_kind: "hidden" },
    ],
    capabilities,
    available_entities: [],
    surface_affordances: [
      {
        surface_id: "home.agent_start",
        affordance_id: "browse_products",
        event: "click",
        capability_id: "catalog.browse",
        operation_id: "catalog.list",
      },
      {
        surface_id: "home.agent_start",
        affordance_id: "view_cart",
        event: "click",
        capability_id: "cart.manage",
        operation_id: "cart.view",
      },
    ],
    navigation: {
      current: { node_id: "home", surface_id: "home.agent_start", deeplink: { url: "/", resumable: true } },
      back_stack: [],
      forward_stack: [],
    },
    navgraph: navgraph("home", "home.agent_start", ["browse", "cart"]),
    surfaces: {
      active: {
        variant: "agent_home",
        surface_id: "home.agent_start",
        props: { setup: { ready: true }, summary: "Ready to browse demo products or inspect the cart." },
      },
    },
  };
}

function productListProjection() {
  return {
    graph_node: "browse",
    legal_operations: [
      { id: "catalog.list", label: "Browse products", can_dispatch_now: true, invocation_kind: "direct", target_node: "browse" },
      { id: "catalog.open", label: "View product", can_dispatch_now: false, invocation_kind: "entity_selector", missing_args: ["entity_key"] },
      { id: "cart.view", label: "View cart", can_dispatch_now: true, invocation_kind: "direct", target_node: "cart" },
      { id: "route.open_node", label: "Open node", can_dispatch_now: true, invocation_kind: "hidden" },
    ],
    capabilities,
    available_entities: [
      { kind: "product", entity_key: "product:entity_public", label: "Medusa T-Shirt", rendered_on: ["browse.product_list"], operations: [{ operation_id: "catalog.open" }] },
    ],
    surface_affordances: [
      {
        surface_id: "browse.product_list",
        affordance_id: "view_product",
        event: "click",
        capability_id: "catalog.browse",
        operation_id: "catalog.open",
        entity_keys: ["product:entity_public"],
      },
    ],
    navigation: {
      current: { node_id: "browse", surface_id: "browse.product_list", deeplink: { url: "/browse", resumable: true } },
      back_stack: [],
      forward_stack: [],
    },
    navgraph: navgraph("browse", "browse.product_list", ["home", "detail", "cart"]),
    surfaces: {
      active: {
        variant: "product_list",
        surface_id: "browse.product_list",
        props: { setup: { ready: true }, products: [product] },
      },
    },
  };
}

function detailProjection() {
  return {
    graph_node: "detail",
    legal_operations: [
      { id: "catalog.list", label: "Browse products", can_dispatch_now: true, invocation_kind: "direct", target_node: "browse" },
      { id: "variant.select", label: "Select variant", can_dispatch_now: false, invocation_kind: "entity_selector", missing_args: ["entity_key"] },
      { id: "cart.view", label: "View cart", can_dispatch_now: true, invocation_kind: "direct", target_node: "cart" },
    ],
    capabilities,
    available_entities: [
      { kind: "variant", entity_key: "variant:entity_public", label: "M", parent_label: "Medusa T-Shirt", rendered_on: ["detail.product_detail"], operations: [{ operation_id: "variant.select" }] },
    ],
    surface_affordances: [
      {
        surface_id: "detail.product_detail",
        affordance_id: "select_variant",
        event: "click",
        capability_id: "product.configure",
        operation_id: "variant.select",
        entity_keys: ["variant:entity_public"],
      },
    ],
    navigation: {
      current: {
        node_id: "detail",
        surface_id: "detail.product_detail",
        deeplink: { url: "/detail/medusa-t-shirt", resumable: true },
      },
      back_stack: [],
      forward_stack: [],
    },
    navgraph: navgraph("detail", "detail.product_detail", ["home", "browse", "cart"]),
    surfaces: {
      active: {
        variant: "product_detail",
        surface_id: "detail.product_detail",
        props: { setup: { ready: true }, product },
      },
    },
  };
}

function cartProjection() {
  return {
    graph_node: "cart",
    legal_operations: [{ id: "catalog.list", label: "Browse products", can_dispatch_now: true, invocation_kind: "direct", target_node: "browse" }],
    capabilities,
    available_entities: [],
    surface_affordances: [],
    navigation: {
      current: { node_id: "cart", surface_id: "cart.cart_summary", deeplink: { url: "/cart", resumable: true } },
      back_stack: [],
      forward_stack: [],
    },
    navgraph: navgraph("cart", "cart.cart_summary", ["home", "browse"]),
    surfaces: {
      active: {
        variant: "cart_summary",
        surface_id: "cart.cart_summary",
        props: { setup: { ready: true }, cart: { items: [] } },
      },
    },
  };
}

describe("Medusa agent chat UI", () => {
  beforeEach(() => {
    let nextId = 0;
    FakeXMLHttpRequest.instances = [];
    window.localStorage.clear();
    window.history.replaceState(null, "", "/");
    vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest);
    vi.stubGlobal("crypto", { randomUUID: () => `test-id-${nextId++}` });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (!url.startsWith("/api/medusa-agent/projection")) {
          return new Response("{}", { status: 404 });
        }
        return new Response(
          JSON.stringify({
            graph_node: "home",
            legal_operations: [],
            surfaces: {
              active: {
                variant: "setup_status",
                props: { setup: { ready: false } },
              },
            },
            navigation: { current: { node_id: "home" }, back_stack: [], forward_stack: [] },
          }),
        );
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  test("first screen is chat, not a landing page or debugger", () => {
    render(<App />);

    expect(screen.getByRole("textbox", { name: /message/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
    expect(screen.queryByText(/landing|debugger|manifest|dispatch|operation|routedeck/i)).not.toBeInTheDocument();
  });

  test("renders setup status without replacing the chat-first screen", async () => {
    render(<App />);

    expect(screen.getByRole("textbox", { name: /message/i })).toBeInTheDocument();
    expect(await screen.findByText("Setup")).toBeInTheDocument();
    expect(screen.getByText("Needs local demo Medusa")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /refresh|switch|dispatch/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/checkout|cart|payment|admin/i)).not.toBeInTheDocument();
  });

  test("root browser path requests the home projection instead of the previous session node", async () => {
    window.history.replaceState(null, "", "/");
    const fetchMock = vi.fn(async (url: string) => {
      if (url.startsWith("/api/medusa-agent/projection")) {
        expect(url).toContain("rd_node=home");
        return new Response(JSON.stringify(homeProjection()));
      }
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("button", { name: /inspect home, current/i })).toBeInTheDocument();
    expect(`${window.location.pathname}${window.location.search}`).toBe("/");
  });

  test("starts as an assistant chat turn with starter action chips", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/api/medusa-agent/projection")) {
          return new Response(JSON.stringify(homeProjection()));
        }
        return new Response("{}", { status: 404 });
      }),
    );

    render(<App />);

    const chatStream = screen.getByTestId("medusa-chat-stream");
    const starterMessage = await within(chatStream).findByTestId("medusa-starter-message");
    expect(starterMessage).toHaveClass("message-row", "assistant");
    expect(within(starterMessage).getByText("Ask about products, styles, sizing, or what to look at first.")).toBeInTheDocument();
    expect(within(starterMessage).getByTestId("medusa-chat-action-chips")).toBeInTheDocument();
    expect(within(starterMessage).getByRole("button", { name: "Browse products" })).toBeInTheDocument();
    expect(within(starterMessage).getByRole("button", { name: "View cart" })).toBeInTheDocument();
    const shoppingSurface = within(chatStream).getByRole("region", { name: /shopping surface/i });
    expect(starterMessage.compareDocumentPosition(shoppingSurface) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test("renders product list, separated read-only graph, inspector, and useful chat action chips", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/api/medusa-agent/projection")) {
          return new Response(JSON.stringify(productListProjection()));
        }
        return new Response("{}", { status: 404 });
      }),
    );

    render(<App />);

    expect(screen.getByRole("textbox", { name: /message/i })).toBeInTheDocument();
    const productTitle = await screen.findByRole("heading", { name: "Medusa T-Shirt" });
    const chatPrompt = screen.getByText("Ask about products, styles, sizing, or what to look at first.");
    expect(chatPrompt.compareDocumentPosition(productTitle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const chatStream = screen.getByTestId("medusa-chat-stream");
    const shoppingSurface = within(chatStream).getByRole("region", { name: /shopping surface/i });
    const agentContext = screen.getByRole("complementary", { name: /agent context/i });
    expect(chatStream).toContainElement(shoppingSurface);
    expect(within(shoppingSurface).getByRole("button", { name: /view medusa t-shirt/i })).toBeInTheDocument();
    expect(within(agentContext).queryByRole("heading", { name: "Medusa T-Shirt" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: /agent route map/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /routedeck navigation graph/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /open/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /inspect browse, current/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /inspect product detail, reachable/i })).toBeInTheDocument();
    expect(within(chatStream).getByTestId("medusa-chat-action-chips")).toBeInTheDocument();
    expect(within(chatStream).queryByRole("button", { name: "Browse products" })).not.toBeInTheDocument();
    expect(within(chatStream).getByRole("button", { name: "View cart" })).toBeInTheDocument();
    expect(within(agentContext).queryByTestId("medusa-chat-action-chips")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open node" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: /route inspector/i })).toBeInTheDocument();
    expect(screen.getByText("Browse catalog")).toBeInTheDocument();
    expect(screen.getByText("Open product from surface")).toBeInTheDocument();
    expect(screen.queryByText(/catalog.open|entity_public|routedeck|dispatch|graph_node/i)).not.toBeInTheDocument();
  });

  test("navgraph node selection updates only the read-only inspector", async () => {
    window.history.replaceState(null, "", "/browse");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/api/medusa-agent/projection")) {
          return new Response(JSON.stringify(productListProjection()));
        }
        return new Response("{}", { status: 404 });
      }),
    );

    render(<App />);

    await screen.findByRole("button", { name: /inspect product detail, reachable/i });
    fireEvent.click(screen.getByRole("button", { name: /inspect product detail, reachable/i }));

    expect(`${window.location.pathname}${window.location.search}`).toBe("/browse");
    expect(screen.getByText("Choose product options")).toBeInTheDocument();
    expect(screen.getByText("/detail/medusa-t-shirt")).toBeInTheDocument();
  });

  test("pasted path deeplink is sent to projection and reflected in the address bar", async () => {
    window.history.replaceState(null, "", "/detail/medusa-t-shirt");
    const fetchMock = vi.fn(async (url: string) => {
      if (url.startsWith("/api/medusa-agent/projection")) {
        expect(url).toContain("rd_node=detail");
        expect(url).toContain("rd_product=medusa-t-shirt");
        return new Response(JSON.stringify(detailProjection()));
      }
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText("Current product")).toBeInTheDocument();
    expect(screen.getByText("Medusa T-Shirt")).toBeInTheDocument();
    await waitFor(() => expect(`${window.location.pathname}${window.location.search}`).toBe("/detail/medusa-t-shirt"));
  });

  test("legacy query deeplink still resumes and normalizes to the product path", async () => {
    window.history.replaceState(null, "", "/?rd_node=detail&rd_product=medusa-t-shirt");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/api/medusa-agent/projection")) {
          expect(url).toContain("rd_node=detail");
          expect(url).toContain("rd_product=medusa-t-shirt");
          return new Response(JSON.stringify(detailProjection()));
        }
        return new Response("{}", { status: 404 });
      }),
    );

    render(<App />);

    expect(await screen.findByText("Current product")).toBeInTheDocument();
    await waitFor(() => expect(`${window.location.pathname}${window.location.search}`).toBe("/detail/medusa-t-shirt"));
  });

  test("view product click dispatches surface event through generic RouteDeck endpoint", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.startsWith("/api/medusa-agent/projection")) {
        return new Response(JSON.stringify(productListProjection()));
      }
      if (url === "/api/medusa-agent/action") {
        expect(JSON.parse(String(init?.body))).toMatchObject({
          surface_event: {
            surface_id: "browse.product_list",
            affordance_id: "view_product",
            entity_key: "product:entity_public",
          },
          context: { source: "ui" },
        });
        expect(String(init?.body)).not.toContain("product_ref");
        return new Response(JSON.stringify({ accepted: true, state: { projection: detailProjection() } }));
      }
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /view medusa t-shirt/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/medusa-agent/action", expect.objectContaining({ method: "POST" }));
    });
    await waitFor(() => expect(`${window.location.pathname}${window.location.search}`).toBe("/detail/medusa-t-shirt"));
  });

  test("active commerce surface is embedded in the chat stream, not beside it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/api/medusa-agent/projection")) {
          return new Response(JSON.stringify(productListProjection()));
        }
        return new Response("{}", { status: 404 });
      }),
    );

    render(<App />);

    const chatStream = screen.getByTestId("medusa-chat-stream");
    const starterMessage = await within(chatStream).findByTestId("medusa-starter-message");
    const shoppingSurface = within(chatStream).getByRole("region", { name: /shopping surface/i });
    expect(chatStream).toContainElement(shoppingSurface);
    expect(starterMessage.compareDocumentPosition(shoppingSurface) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(shoppingSurface).getByRole("heading", { name: "Medusa T-Shirt" })).toBeInTheDocument();

    const workspace = screen.getByTestId("medusa-agent-workspace");
    expect(workspace).toContainElement(chatStream);
    expect(workspace).toContainElement(screen.getByRole("complementary", { name: /agent context/i }));
    expect(within(screen.getByRole("complementary", { name: /agent context/i })).queryByRole("region", { name: /shopping surface/i })).not.toBeInTheDocument();
  });

  test("chat action chip dispatches separately from the read-only navgraph", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.startsWith("/api/medusa-agent/projection")) {
        return new Response(JSON.stringify(homeProjection()));
      }
      if (url === "/api/medusa-agent/action") {
        expect(JSON.parse(String(init?.body))).toMatchObject({
          operation_id: "cart.view",
          args: {},
          context: { source: "ui" },
        });
        expect(String(init?.body)).not.toContain("surface_event");
        return new Response(JSON.stringify({ accepted: true, state: { projection: cartProjection() } }));
      }
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    const chatStream = await screen.findByTestId("medusa-chat-stream");
    const agentContext = await screen.findByRole("complementary", { name: /agent context/i });
    const chipPanel = within(chatStream).getByTestId("medusa-chat-action-chips");
    expect(chipPanel).toBeInTheDocument();
    expect(within(agentContext).queryByTestId("medusa-chat-action-chips")).not.toBeInTheDocument();
    fireEvent.click(within(chipPanel).getByRole("button", { name: "View cart" }));

    await waitFor(() => expect(`${window.location.pathname}${window.location.search}`).toBe("/cart"));
    expect(await screen.findByRole("button", { name: /inspect cart, current/i })).toBeInTheDocument();
    expect(await screen.findByText("No items selected yet.")).toBeInTheDocument();
  });

  test("sending hi posts to the app-owned stream endpoint", () => {
    render(<App />);

    fireEvent.change(screen.getByRole("textbox", { name: /message/i }), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    const xhr = FakeXMLHttpRequest.instances[0];
    expect(xhr.method).toBe("POST");
    expect(xhr.url).toBe("/api/medusa-agent/agent/stream");
    expect(JSON.parse(xhr.requestBody)).toEqual({
      message: "hi",
      conversation_id: null,
      session_id: "session-test-id-0",
    });
    expect(screen.getByLabelText("Assistant is preparing a response")).toBeInTheDocument();
    expect(screen.getByText("Checking context")).toBeInTheDocument();
    expect(screen.getByText("Reviewing options")).toBeInTheDocument();
    expect(screen.getByText("Preparing reply")).toBeInTheDocument();
  });

  test("parses true SSE chunks and appends message_delta incrementally", async () => {
    render(<App />);

    fireEvent.change(screen.getByRole("textbox", { name: /message/i }), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    const xhr = FakeXMLHttpRequest.instances[0];
    xhr.push('event: stream_start\ndata: {"conversation_id":"chat-1","model":"gpt-5-mini"}\n\n');
    xhr.push('event: agent_start\ndata: {"agent_name":"medusa-commerce-agent"}\n\n');
    xhr.push('event: message_delta\ndata: {"content":"Hi. "}\n\n');

    expect(await screen.findByText("Hi.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Assistant is preparing a response")).not.toBeInTheDocument();

    xhr.push('event: message_delta\ndata: {"content":"I can help you shop."}\n\n');
    expect(await screen.findByText("Hi. I can help you shop.")).toBeInTheDocument();

    xhr.push("event: agent_end\ndata: {}\n\n");
    xhr.push("event: stream_end\ndata: {}\n\n");
    xhr.finish();

    await waitFor(() => expect(screen.getByText("Ready")).toBeInTheDocument());
    expect(screen.getByRole("textbox", { name: /message/i })).not.toBeDisabled();
  });

  test("chat RouteDeck event updates projection and deeplink without navgraph click", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/api/medusa-agent/projection")) {
          return new Response(JSON.stringify(homeProjection()));
        }
        return new Response("{}", { status: 404 });
      }),
    );

    render(<App />);

    expect(await screen.findByRole("button", { name: /inspect home, current/i })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: /message/i }), {
      target: { value: "show me products" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    const xhr = FakeXMLHttpRequest.instances[0];
    xhr.push('event: stream_start\ndata: {"conversation_id":"chat-1","model":"gpt-5-mini"}\n\n');
    xhr.push('event: agent_start\ndata: {"agent_name":"medusa-commerce-agent"}\n\n');
    xhr.push(
      `event: routedeck_event\ndata: ${JSON.stringify({
        event_type: "operation_completed",
        projection_version: 2,
        payload: { operation_id: "catalog.list", state: { projection: productListProjection(), status: "idle" } },
      })}\n\n`,
    );
    xhr.push('event: message_delta\ndata: {"content":"I found 1 product."}\n\n');
    xhr.push("event: stream_end\ndata: {}\n\n");
    xhr.finish();

    expect(await screen.findByText("I found 1 product.")).toBeInTheDocument();
    await waitFor(() => expect(`${window.location.pathname}${window.location.search}`).toBe("/browse"));
    expect(screen.getByRole("button", { name: /inspect browse, current/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Medusa T-Shirt" })).toBeInTheDocument();
  });

  test("parseSSEFrames keeps partial frames buffered until complete", () => {
    const first = parseSSEFrames('event: message_delta\ndata: {"content":"Hel', "");
    expect(first.events).toEqual([]);

    const second = parseSSEFrames('lo"}\n\n', first.buffer);
    expect(second.events).toEqual([{ event: "message_delta", data: { content: "Hello" } }]);
    expect(second.buffer).toBe("");
  });
});
