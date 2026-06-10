import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

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

describe("Medusa Slice 1 chat-first UI", () => {
  beforeEach(() => {
    let nextId = 0;
    FakeXMLHttpRequest.instances = [];
    vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest);
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.startsWith("/api/medusa-agent/projection")) {
        return {
          ok: true,
          status: 200,
          json: async () => projectionFixture("home"),
        };
      }
      if (url.startsWith("/api/medusa-agent/debug/context-thread")) {
        return {
          ok: true,
          status: 200,
          json: async () => debugContextFixture("chat-1"),
        };
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    vi.stubGlobal("crypto", { randomUUID: () => `test-id-${nextId++}` });
    window.history.replaceState({}, "", "/");
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  test("first screen keeps the Foundation-style chat shell and projection-backed route context", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Medusa Agent" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new chat/i })).toBeInTheDocument();
    expect(screen.getByTestId("medusa-agent-workspace")).toBeInTheDocument();
    expect(screen.getByTestId("medusa-starter-message")).toBeInTheDocument();
    expect(screen.getByTestId("starter-chat-actions")).toBeInTheDocument();
    expect(await screen.findByTestId("medusa-projected-surface")).toBeInTheDocument();
    expect(screen.getByText("Medusa shopping surface")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /message/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();

    expect(screen.getByText("Route Map")).toBeInTheDocument();
    expect(screen.getByTestId("route-map-graph")).toBeInTheDocument();
    expect(screen.getByTestId("route-edge-home-browse")).toBeInTheDocument();
    expect(screen.getByTestId("route-edge-browse-detail")).toBeInTheDocument();
    expect(screen.getByTestId("route-edge-detail-cart")).toBeInTheDocument();
    expect(screen.getByText("Inspector")).toBeInTheDocument();
    expect(screen.getAllByText("Home").length).toBeGreaterThan(0);
    expect(screen.getByText("Browse")).toBeInTheDocument();
    expect(screen.getByText("Detail")).toBeInTheDocument();
    expect(screen.getByText("Cart")).toBeInTheDocument();
    expect(await screen.findByText(/Projection-backed orientation/i)).toBeInTheDocument();
    expect(screen.getByText("surface_id")).toBeInTheDocument();
    expect(screen.getByText("home.chat")).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: /add.*cart|checkout|admin|view product/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/store api|surface_event|operation_id|private id/i)).not.toBeInTheDocument();
  });

  test("frontend fetches only the product-owned projection endpoint on load", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.startsWith("/api/medusa-agent/projection")) {
        return {
          ok: true,
          status: 200,
          json: async () => projectionFixture("home"),
        };
      }
      if (url.startsWith("/api/medusa-agent/debug/context-thread")) {
        return {
          ok: true,
          status: 200,
          json: async () => debugContextFixture("chat-1"),
        };
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const calledUrl = String(fetchMock.mock.calls[0][0]);
    expect(calledUrl).toBe("/api/medusa-agent/projection?path=%2F");
    expect(calledUrl).not.toContain("/api/routedeck");
    expect(calledUrl).not.toContain("/action");
    expect(calledUrl).not.toContain("/inspect");
  });

  test("route map selection updates only local inspector focus", async () => {
    const fetchMock = vi.mocked(fetch);
    render(<App />);

    await screen.findByText("home.chat");
    const beforeUrl = window.location.href;

    expect(screen.getByTestId("route-map-graph")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Browse" }));

    expect(window.location.href).toBe(beforeUrl);
    expect(screen.getByText("browse.product_list")).toBeInTheDocument();
    expect(screen.getByText("/browse")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("sending a message posts only to the app-owned chat stream endpoint", () => {
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
      route_context: {
        path: "/",
        surface_id: "home.chat",
      },
    });
    expect(screen.getByLabelText("Assistant is preparing a response")).toBeInTheDocument();
  });

  test("composer prompt chips are projected by the backend and still send ordinary chat SSE messages", async () => {
    render(<App />);

    expect(await screen.findByRole("button", { name: "Show me products" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /gift ideas/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show me products" }));

    const xhr = FakeXMLHttpRequest.instances[0];
    expect(xhr.method).toBe("POST");
    expect(xhr.url).toBe("/api/medusa-agent/agent/stream");
    expect(JSON.parse(xhr.requestBody)).toEqual({
      message: "Show me products in the current Medusa catalog",
      conversation_id: null,
      route_context: {
        path: "/",
        surface_id: "home.chat",
      },
    });
    expect(screen.getByText("Show me products in the current Medusa catalog")).toBeInTheDocument();
  });

  test("chat submit applies projection metadata from SSE and updates the visible browse path", async () => {
    render(<App />);

    expect(await screen.findByText("home.chat")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: /message/i }), {
      target: { value: "show products" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    const xhr = FakeXMLHttpRequest.instances[0];
    expect(JSON.parse(xhr.requestBody)).toEqual({
      message: "show products",
      conversation_id: null,
      route_context: {
        path: "/",
        surface_id: "home.chat",
      },
    });

    pushBrowseProjectionUpdate(xhr);
    xhr.finish();

    await waitFor(() => expect(window.location.pathname).toBe("/browse"));
    expect(screen.getByText("browse.product_list")).toBeInTheDocument();
    expect(screen.getByText("/browse")).toBeInTheDocument();
    expect(screen.getByTestId("medusa-projected-surface")).toHaveTextContent("Projection-only Linen Overshirt");
    expect(screen.getByTestId("medusa-projected-surface")).toHaveTextContent(
      "Projection payload fact, not fallback fixture copy.",
    );
    expect(screen.getByTestId("debug-context-card")).toHaveTextContent("accepted_intent");
    expect(screen.getByTestId("debug-context-card")).toHaveTextContent("browse_products");
    expect(screen.getByTestId("debug-context-card")).toHaveTextContent("projection_version");
    expect(screen.getByTestId("debug-context-card")).toHaveTextContent("2");
  });

  test("projected Show products action chip converges on the same browse projection update", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Show me products" }));

    const xhr = FakeXMLHttpRequest.instances[0];
    expect(JSON.parse(xhr.requestBody)).toEqual({
      message: "Show me products in the current Medusa catalog",
      conversation_id: null,
      route_context: {
        path: "/",
        surface_id: "home.chat",
      },
    });

    pushBrowseProjectionUpdate(xhr);
    xhr.finish();

    await waitFor(() => expect(window.location.pathname).toBe("/browse"));
    expect(screen.getByText("browse.product_list")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Compare projection-only facts" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show me products" })).not.toBeInTheDocument();
    expect(screen.getByTestId("medusa-projected-surface")).toHaveTextContent("Projection-only Linen Overshirt");
  });

  test("detail deeplink renders projected product surface inside the chat stream", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.startsWith("/api/medusa-agent/projection")) {
        return {
          ok: true,
          status: 200,
          json: async () => projectionFixture("detail"),
        };
      }
      if (url.startsWith("/api/medusa-agent/debug/context-thread")) {
        return {
          ok: true,
          status: 200,
          json: async () => debugContextFixture("chat-1"),
        };
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState({}, "", "/detail/t-shirt?surface_id=detail.product_detail");

    render(<App />);

    await waitFor(() =>
      expect(String(fetchMock.mock.calls[0][0])).toBe(
        "/api/medusa-agent/projection?path=%2Fdetail%2Ft-shirt&surface_id=detail.product_detail",
      ),
    );
    const surface = await screen.findByTestId("medusa-projected-surface");
    expect(surface).toHaveTextContent("Projected product surface");
    expect(surface).toHaveTextContent("Medusa T-Shirt");
    expect(surface).toHaveTextContent("$48.00");
    expect(surface).toHaveTextContent("Read-only detail surface for Medusa T-Shirt.");
    expect(screen.getByText("detail.product_detail")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add.*cart|checkout|admin/i })).not.toBeInTheDocument();
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

  test("missing-key SSE error is shown as assistant text without fake fallback content", async () => {
    render(<App />);

    fireEvent.change(screen.getByRole("textbox", { name: /message/i }), {
      target: { value: "show me products" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    const xhr = FakeXMLHttpRequest.instances[0];
    xhr.push('event: stream_start\ndata: {"conversation_id":"chat-1","model":"gpt-5-mini"}\n\n');
    xhr.push('event: agent_start\ndata: {"agent_name":"medusa-commerce-agent"}\n\n');
    xhr.push('event: error\ndata: {"message":"OPENAI_API_KEY is required for the Medusa agent.","code":"openai_api_key_missing"}\n\n');
    xhr.push("event: agent_end\ndata: {}\n\n");
    xhr.push("event: stream_end\ndata: {}\n\n");
    xhr.finish();

    expect(await screen.findByText("OPENAI_API_KEY is required for the Medusa agent.")).toBeInTheDocument();
    expect(screen.queryByText(/here are products|added to cart|checkout/i)).not.toBeInTheDocument();
  });

  test("parseSSEFrames keeps partial frames buffered until complete", () => {
    const first = parseSSEFrames('event: message_delta\ndata: {"content":"Hel', "");
    expect(first.events).toEqual([]);

    const second = parseSSEFrames('lo"}\n\n', first.buffer);
    expect(second.events).toEqual([{ event: "message_delta", data: { content: "Hello" } }]);
    expect(second.buffer).toBe("");
  });

  test("temporary debug view shows full context thread including system prompt after streaming", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.startsWith("/api/medusa-agent/projection")) {
        return {
          ok: true,
          status: 200,
          json: async () => projectionFixture("detail"),
        };
      }
      if (url.startsWith("/api/medusa-agent/debug/context-thread")) {
        expect(url).toContain("conversation_id=chat-1");
        return {
          ok: true,
          status: 200,
          json: async () => debugContextFixture("chat-1"),
        };
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState({}, "", "/detail/t-shirt?surface_id=detail.product_detail");

    render(<App />);

    expect(await screen.findByText("Debug Context")).toBeInTheDocument();
    expect(screen.getByText("No conversation captured yet.")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: /message/i }), {
      target: { value: "what products do we have?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    const xhr = FakeXMLHttpRequest.instances[0];
    xhr.push('event: stream_start\ndata: {"conversation_id":"chat-1","model":"gpt-5-mini"}\n\n');
    xhr.push('event: agent_start\ndata: {"agent_name":"medusa-commerce-agent"}\n\n');
    xhr.push('event: message_delta\ndata: {"content":"Two products."}\n\n');
    xhr.push("event: agent_end\ndata: {}\n\n");
    xhr.push("event: stream_end\ndata: {}\n\n");
    xhr.finish();

    expect(await screen.findByText("Commerce system prompt")).toBeInTheDocument();
    expect(screen.getByText(/You are the Medusa demo shopping assistant/i)).toBeInTheDocument();
    expect(screen.getByText("RouteDeck planning context")).toBeInTheDocument();
    expect(screen.getAllByText(/detail.product_detail/i).length).toBeGreaterThan(0);
    expect(screen.getByText("User")).toBeInTheDocument();
    expect(screen.getAllByText(/what products do we have/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Assistant")).toBeInTheDocument();
    expect(screen.getAllByText(/Two products/i).length).toBeGreaterThan(0);
  });

  test("runtime frontend source has no fake dispatch, Store API, write, or private-id drift", () => {
    const sourceFiles = [
      join(process.cwd(), "src", "App.tsx"),
      join(process.cwd(), "src", "hooks", "useSSEChat.ts"),
      join(process.cwd(), "src", "main.tsx"),
      join(process.cwd(), "src", "styles.css"),
    ];
    const forbidden = /dispatch|Store API|surface_event|operation_id|@medusajs|\/api\/medusa-agent\/(action|inspect|route-stream)|\/api\/routedeck|checkout|admin|add selected|add to cart|catalog\.|cart\.(?:create|add_item|view)|prod_|variant_private|cart_private|line_private/i;
    const hits = sourceFiles.filter((path) => forbidden.test(readFileSync(path, "utf8")));

    expect(hits).toEqual([]);
  });

  test("layout pins the composer in the viewport instead of forcing page scroll", () => {
    const css = readFileSync(join(process.cwd(), "src", "styles.css"), "utf8");

    expect(css).toMatch(/body\s*{[\s\S]*overflow:\s*hidden/);
    expect(css).toMatch(/\.app-shell\s*{[\s\S]*height:\s*100dvh/);
    expect(css).toMatch(/\.app-shell\s*{[\s\S]*overflow:\s*hidden/);
    expect(css).toMatch(/\.conversation-shell\s*{[\s\S]*height:\s*100%/);
    expect(css).toMatch(/\.chat-scroll\s*{[\s\S]*min-height:\s*0/);
    expect(css).toMatch(/\.input-dock\s*{[\s\S]*position:\s*relative/);
  });

  test("tablet layout keeps the page locked while rail content scrolls internally", () => {
    const css = readFileSync(join(process.cwd(), "src", "styles.css"), "utf8");
    const tabletStart = css.indexOf("@media (max-width: 980px)");
    const phoneStart = css.indexOf("@media (max-width: 680px)");
    const tabletBlock = css.slice(tabletStart, phoneStart);

    expect(tabletBlock).toContain("@media (max-width: 980px)");
    expect(tabletBlock).toMatch(/body\s*{[\s\S]*overflow:\s*hidden/);
    expect(tabletBlock).toMatch(/\.app-shell\s*{[\s\S]*height:\s*100dvh/);
    expect(tabletBlock).toMatch(/\.app-shell\s*{[\s\S]*overflow:\s*hidden/);
    expect(tabletBlock).toMatch(/\.context-rail\s*{[\s\S]*overflow-y:\s*auto/);
  });
});

function projectionFixture(node: "home" | "browse" | "detail" | "cart") {
  const surfaceByNode = {
    home: "home.chat",
    browse: "browse.product_list",
    detail: "detail.product_detail",
    cart: "cart.summary",
  };
  const pathByNode = {
    home: "/",
    browse: "/browse",
    detail: "/detail/t-shirt",
    cart: "/cart",
  };

  return {
    current_context: node,
    graph_node: node,
    projection_version: 1,
    legal_operations: [],
    surfaces: {
      active: {
        name: "active",
        surface_id: surfaceByNode[node],
        component: componentByNode[node],
        variant: surfaceByNode[node],
        role: "active",
        surface_kind: "embedded",
        label: labelByNode[node],
        props: surfacePropsByNode[node],
      },
    },
    presentation_state: {
      active_surface_id: surfaceByNode[node],
      product_handle: node === "detail" ? "t-shirt" : undefined,
      chat_suggestions: chatSuggestionsByNode[node],
    },
    navigation: {
      current: {
        node_id: node,
        surface_id: surfaceByNode[node],
        params: {},
        deeplink: { url: pathByNode[node], resumable: true },
      },
      back_stack: [],
      forward_stack: [],
      can_back: false,
      can_forward: false,
      can_cancel: false,
    },
    capabilities: [],
    navgraph: {
      current: {
        node_id: node,
        surface_id: surfaceByNode[node],
        params: {},
        deeplink: { url: pathByNode[node], resumable: true },
      },
      nodes: [
        { id: "home", label: "Home", surface_id: "home.chat", deeplink: { url: "/", resumable: true }, capability_ids: [] },
        { id: "browse", label: "Browse", surface_id: "browse.product_list", deeplink: { url: "/browse", resumable: true }, capability_ids: [] },
        { id: "detail", label: "Detail", surface_id: "detail.product_detail", deeplink: { url: "/detail/t-shirt", resumable: true }, capability_ids: [] },
        { id: "cart", label: "Cart", surface_id: "cart.summary", deeplink: { url: "/cart", resumable: true }, capability_ids: [] },
      ],
      edges: [
        { from: "home", to: "browse" },
        { from: "browse", to: "detail" },
        { from: "detail", to: "cart" },
      ],
      traversed: [],
      reachable: node === "home" ? ["browse"] : [],
    },
    available_entities: [
      {
        kind: "product",
        entity_key: "product:t-shirt",
        label: "Medusa T-Shirt",
        rendered_on: ["browse.product_list", "detail.product_detail"],
        operations: [],
        metadata: { handle: "t-shirt", price: "$48.00" },
      },
    ],
    surface_affordances: [],
    diagnostics: {},
  };
}

function debugContextFixture(conversationId: string) {
  return {
    conversation_id: conversationId,
    model: "gpt-5-mini",
    system_prompt: {
      role: "system",
      source: "commerce_system_prompt",
      content: "You are the Medusa demo shopping assistant.",
    },
    latest_route_context: {
      path: "/detail/t-shirt",
      surface_id: "detail.product_detail",
    },
    thread: [
      {
        role: "system",
        source: "routedeck_planning_context",
        content: "Current RouteDeck planning context: surface detail.product_detail",
      },
      {
        role: "user",
        source: "user",
        content: "what products do we have?",
      },
      {
        role: "assistant",
        source: "assistant",
        content: "Two products.",
      },
    ],
  };
}

function pushBrowseProjectionUpdate(xhr: FakeXMLHttpRequest) {
  xhr.push(sseFrame("stream_start", { conversation_id: "chat-1", model: "gpt-5-mini" }));
  xhr.push(sseFrame("agent_start", { agent_name: "medusa-commerce-agent" }));
  xhr.push(
    sseFrame("projection_update", {
      accepted_intent: "browse_products",
      route_context: {
        path: "/browse",
        surface_id: "browse.product_list",
      },
      planning_context: {
        current: {
          node_id: "browse",
          surface_id: "browse.product_list",
          deeplink: "/browse",
        },
        available_entities: [
          {
            kind: "product",
            entity_key: "product:linen-overshirt",
            label: "Projection-only Linen Overshirt",
          },
        ],
      },
      projection_version: 2,
      projection: browseProjectionFromSse(),
    }),
  );
  xhr.push(sseFrame("message_delta", { content: "Here are the products I can show from the current projection." }));
  xhr.push(sseFrame("agent_end", {}));
  xhr.push(sseFrame("stream_end", {}));
}

function sseFrame(event: string, data: Record<string, unknown>) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function browseProjectionFromSse() {
  const projection = projectionFixture("browse") as any;
  projection.projection_version = 2;
  projection.presentation_state.chat_suggestions = [
    {
      label: "Compare projection-only facts",
      message: "Compare the projection-only products that are visible now.",
    },
  ];
  projection.surfaces.active.props.products = [
    {
      handle: "linen-overshirt",
      title: "Projection-only Linen Overshirt",
      price: "$92.00",
      summary: "Projection payload fact, not fallback fixture copy.",
      colors: ["Sage"],
      sizes: ["M"],
    },
  ];
  projection.available_entities = [
    {
      kind: "product",
      entity_key: "product:linen-overshirt",
      label: "Projection-only Linen Overshirt",
      rendered_on: ["browse.product_list"],
      operations: [],
      metadata: { handle: "linen-overshirt", price: "$92.00" },
    },
  ];
  return projection;
}

const componentByNode = {
  home: "MedusaHomeChatSurface",
  browse: "MedusaProductListSurface",
  detail: "MedusaProductDetailSurface",
  cart: "MedusaCartSummarySurface",
};

const labelByNode = {
  home: "Medusa shopping surface",
  browse: "Projected product surface",
  detail: "Projected product surface",
  cart: "Projected cart surface",
};

const chatSuggestionsByNode = {
  home: [{ label: "Show me products", message: "Show me products in the current Medusa catalog" }],
  browse: [{ label: "Compare tee and sweatshirt", message: "Compare the T-shirt and sweatshirt." }],
  detail: [{ label: "Ask about this T-shirt", message: "What should I know about this Medusa T-Shirt?" }],
  cart: [{ label: "Review my cart", message: "Review my current cart summary." }],
};

const product = {
  handle: "t-shirt",
  title: "Medusa T-Shirt",
  price: "$48.00",
  summary: "Premium cotton tee with a relaxed fit.",
};

const surfacePropsByNode = {
  home: {
    path: "/",
    surface_id: "home.chat",
    surface_summary: "Read-only home surface for starting a Medusa shopping conversation.",
  },
  browse: {
    path: "/browse",
    surface_id: "browse.product_list",
    surface_summary: "Read-only browse surface with two Medusa products.",
    products: [
      product,
      {
        handle: "sweatshirt",
        title: "Medusa Sweatshirt",
        price: "$78.00",
        summary: "Soft fleece sweatshirt for everyday comfort.",
      },
    ],
  },
  detail: {
    path: "/detail/t-shirt",
    surface_id: "detail.product_detail",
    surface_summary: "Read-only detail surface for Medusa T-Shirt.",
    product,
  },
  cart: {
    path: "/cart",
    surface_id: "cart.summary",
    surface_summary: "Read-only cart summary surface.",
    cart: { item_count: 0, total: "$0.00" },
  },
};
