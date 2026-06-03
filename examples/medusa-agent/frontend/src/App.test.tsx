import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

describe("Medusa agent chat UI", () => {
  beforeEach(() => {
    let nextId = 0;
    FakeXMLHttpRequest.instances = [];
    window.localStorage.clear();
    vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest);
    vi.stubGlobal("crypto", { randomUUID: () => `test-id-${nextId++}` });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (!url.startsWith("/api/routedeck/projection")) {
          return new Response("{}", { status: 404 });
        }
        return (
        new Response(
          JSON.stringify({
            graph_node: "setup",
            legal_operations: [],
            surfaces: {
              active: {
                variant: "setup_status",
                props: { setup: { ready: false } },
              },
            },
          }),
        )
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
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/api/routedeck/projection")) {
          return new Response(
            JSON.stringify({
              graph_node: "setup",
              legal_operations: [],
              surfaces: {
                active: {
                  variant: "setup_status",
                  props: { setup: { ready: false } },
                },
              },
              navigation: { current: { node_id: "setup" }, back_stack: [], forward_stack: [] },
            }),
          );
        }
        return new Response("{}", { status: 404 });
      }),
    );

    render(<App />);

    expect(screen.getByRole("textbox", { name: /message/i })).toBeInTheDocument();
    expect(await screen.findByText("Setup")).toBeInTheDocument();
    expect(screen.getByText("Needs local demo Medusa")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /refresh|switch|dispatch/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/checkout|cart|payment|admin/i)).not.toBeInTheDocument();
  });

  test("renders product list from projection without RouteDeck internals", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/api/routedeck/projection")) {
          return new Response(
            JSON.stringify({
              graph_node: "browse",
              legal_operations: [{ id: "catalog.open", label: "View product" }],
              surfaces: {
                active: {
                  variant: "product_list",
                  props: {
                    setup: { ready: true },
                    products: [
                      {
                        product_ref: "p_ref",
                        title: "Medusa T-Shirt",
                        thumbnail: "https://example.test/shirt.png",
                        variants: [{ variant_ref: "v_ref", title: "M" }],
                      },
                    ],
                  },
                },
              },
              navigation: { current: { node_id: "browse" }, back_stack: [], forward_stack: [] },
            }),
          );
        }
        return new Response("{}", { status: 404 });
      }),
    );

    render(<App />);

    expect(screen.getByRole("textbox", { name: /message/i })).toBeInTheDocument();
    expect(await screen.findByText("Medusa T-Shirt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view medusa t-shirt/i })).toBeInTheDocument();
    expect(screen.queryByText(/catalog.open|p_ref|v_ref|routedeck|dispatch|graph_node/i)).not.toBeInTheDocument();
  });

  test("view product click dispatches through generic RouteDeck endpoint", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.startsWith("/api/routedeck/projection")) {
        return new Response(
          JSON.stringify({
            graph_node: "browse",
            legal_operations: [{ id: "catalog.open", label: "View product" }],
            surfaces: {
              active: {
                variant: "product_list",
                props: {
                  setup: { ready: true },
                  products: [{ product_ref: "p_ref", title: "Medusa T-Shirt" }],
                },
              },
            },
            navigation: { current: { node_id: "browse" }, back_stack: [], forward_stack: [] },
          }),
        );
      }
      if (url === "/api/routedeck/dispatch") {
        expect(JSON.parse(String(init?.body))).toMatchObject({
          operation_id: "catalog.open",
          args: { product_ref: "p_ref" },
          context: { source: "ui" },
        });
        return new Response(JSON.stringify({ accepted: true }));
      }
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /view medusa t-shirt/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/routedeck/dispatch", expect.objectContaining({ method: "POST" }));
    });
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
    expect(JSON.parse(xhr.requestBody)).toEqual({ message: "hi", conversation_id: null });
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

    xhr.push('event: message_delta\ndata: {"content":"I can help you shop."}\n\n');
    expect(await screen.findByText("Hi. I can help you shop.")).toBeInTheDocument();

    xhr.push("event: agent_end\ndata: {}\n\n");
    xhr.push("event: stream_end\ndata: {}\n\n");
    xhr.finish();

    await waitFor(() => expect(screen.getByText("Ready")).toBeInTheDocument());
    expect(screen.getByRole("textbox", { name: /message/i })).not.toBeDisabled();
  });

  test("parseSSEFrames keeps partial frames buffered until complete", () => {
    const first = parseSSEFrames('event: message_delta\ndata: {"content":"Hel', "");
    expect(first.events).toEqual([]);

    const second = parseSSEFrames('lo"}\n\n', first.buffer);
    expect(second.events).toEqual([{ event: "message_delta", data: { content: "Hello" } }]);
    expect(second.buffer).toBe("");
  });
});
