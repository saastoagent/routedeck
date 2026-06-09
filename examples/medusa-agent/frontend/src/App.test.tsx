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
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("crypto", { randomUUID: () => `test-id-${nextId++}` });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  test("first screen copies the Foundation Agent chat shell with read-only RouteDeck vision context", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Medusa Agent" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new chat/i })).toBeInTheDocument();
    expect(screen.getByText(/Start with normal shopping chat/i)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /message/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();

    expect(screen.getByText("Route Map")).toBeInTheDocument();
    expect(screen.getByText("Inspector")).toBeInTheDocument();
    expect(screen.getAllByText("Home").length).toBeGreaterThan(0);
    expect(screen.getByText("Browse")).toBeInTheDocument();
    expect(screen.getByText("Detail")).toBeInTheDocument();
    expect(screen.getByText("Cart")).toBeInTheDocument();
    expect(screen.getByText(/Read-only orientation/i)).toBeInTheDocument();
    expect(screen.getByText("surface_id")).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: /add.*cart|checkout|admin|view product/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/store api|surface_event|operation_id|private id/i)).not.toBeInTheDocument();
  });

  test("frontend does not fetch projection or action endpoints on load", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(fetchMock).not.toHaveBeenCalled();
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
    });
    expect(screen.getByLabelText("Assistant is preparing a response")).toBeInTheDocument();
  });

  test("composer prompt chips still send ordinary chat SSE messages", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /gift ideas/i }));

    const xhr = FakeXMLHttpRequest.instances[0];
    expect(xhr.method).toBe("POST");
    expect(xhr.url).toBe("/api/medusa-agent/agent/stream");
    expect(JSON.parse(xhr.requestBody)).toEqual({
      message: "Help me choose a good gift.",
      conversation_id: null,
    });
    expect(screen.getByText("Help me choose a good gift.")).toBeInTheDocument();
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

  test("runtime frontend source has no fake dispatch, Store API, write, or private-id drift", () => {
    const sourceFiles = [
      join(process.cwd(), "src", "App.tsx"),
      join(process.cwd(), "src", "hooks", "useSSEChat.ts"),
      join(process.cwd(), "src", "main.tsx"),
      join(process.cwd(), "src", "styles.css"),
    ];
    const forbidden = /RouteDeck|routedeck|projection|dispatch|Store API|surface_event|operation_id|@medusajs|\/api\/medusa-agent\/(projection|action|inspect|route-stream)|\/api\/routedeck|checkout|admin|add selected|add to cart|catalog\.|cart\.(?:create|add_item|view)|prod_|variant_private|cart_private|line_private/i;
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
});
