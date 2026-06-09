import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { THINKING_PLACEHOLDER, useSSEChat } from "./hooks/useSSEChat";

const PROMPTS = [
  { label: "Gift ideas", message: "Help me choose a good gift." },
  { label: "Compare staples", message: "Compare a tee and a sweatshirt for everyday wear." },
  { label: "Sizing help", message: "What should I consider before choosing a size?" },
];

const ROUTE_NODES = [
  { id: "home", label: "Home" },
  { id: "browse", label: "Browse" },
  { id: "detail", label: "Detail" },
  { id: "cart", label: "Cart" },
];

type RouteContext = {
  node: string;
  label: string;
  path: string;
  surfaceId: string;
};

export default function App() {
  const [draft, setDraft] = useState("");
  const { messages, isStreaming, sendMessage, clearMessages } = useSSEChat();
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const routeContext = useMemo(() => readRouteContext(), []);

  useEffect(() => {
    if (typeof messageEndRef.current?.scrollIntoView === "function") {
      messageEndRef.current.scrollIntoView({ block: "end" });
    }
  }, [messages]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    sendDraft();
  };

  const sendDraft = () => {
    const next = draft.trim();
    if (!next || isStreaming) return;
    sendMessage(next);
    setDraft("");
  };

  const sendPrompt = (message: string) => {
    if (isStreaming) return;
    sendMessage(message);
  };

  return (
    <main className="app-shell">
      <section className="conversation-shell" aria-label="Medusa commerce chat">
        <header className="topbar">
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">
              M
            </div>
            <div>
              <p className="eyebrow">Slice 1 chat-first proof</p>
              <h1>Medusa Agent</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <span className={isStreaming ? "status status-live" : "status"} aria-live="polite">
              {isStreaming ? "Streaming" : "Ready"}
            </span>
            <button className="ghost-button" type="button" onClick={clearMessages}>
              New chat
            </button>
          </div>
        </header>

        <div className="chat-scroll" aria-live="polite" data-testid="medusa-chat-stream">
          <div className="empty-hero">
            <div className="mini-orbit" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <p className="eyebrow">Start with normal shopping chat</p>
            <h2>Ask, narrow, compare, then let surfaces arrive when the runtime earns them.</h2>
            <p>
              This shell keeps the agent conversation primary while the route context stays
              read-only until later slices add validated surface events.
            </p>
          </div>

          <MessageBubble
            role="assistant"
            content="Tell me what you are shopping for. I can help compare styles, explain sizing, or turn a vague gift idea into a short shortlist."
            timestamp="Now"
          />

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
          <div className="prompt-row" aria-label="Prompt suggestions">
            {PROMPTS.map((prompt) => (
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
              id="message"
              aria-label="Message"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
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
        <section className="context-card">
          <div className="card-title-row">
            <div>
              <p className="eyebrow">Read-only orientation</p>
              <h2>Route Map</h2>
            </div>
            <span className="rail-pill">No actions</span>
          </div>

          <div className="route-map" aria-label="Route Map">
            {ROUTE_NODES.map((node) => (
              <div
                className={node.id === routeContext.node ? "route-node route-node-current" : "route-node"}
                key={node.id}
              >
                <span className="route-dot" aria-hidden="true" />
                <span>{node.label}</span>
              </div>
            ))}
          </div>

          <p className="rail-note">
            Map selection is intentionally inert here. Chat is the only active behavior in
            this slice.
          </p>
        </section>

        <section className="context-card">
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
              <dd>Chat SSE only</dd>
            </div>
          </dl>
        </section>
      </aside>
    </main>
  );
}

function MessageBubble({
  role,
  content,
  timestamp,
  isStreaming = false,
}: {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  isStreaming?: boolean;
}) {
  const isUser = role === "user";
  const showThinking = isStreaming && content === THINKING_PLACEHOLDER;

  return (
    <div className={isUser ? "message-row user" : "message-row assistant"}>
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
  const label = ROUTE_NODES.find((item) => item.id === node)?.label || "Home";

  return {
    node,
    label,
    path,
    surfaceId,
  };
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
