import { useEffect, useRef, type ReactNode } from "react";

import type {
  AgentConversationMessage,
  AgentStreamStatus,
} from "../app/useAgentStream";

export interface ConversationProps {
  messages: readonly AgentConversationMessage[];
  status: AgentStreamStatus;
  activeSurface: ReactNode;
}

export function Conversation({
  messages,
  status,
  activeSurface,
}: ConversationProps) {
  const activityAnchor = useRef<HTMLLIElement>(null);
  const hasStreamingAssistant = messages.some(
    (message) =>
      message.role === "assistant" && message.status === "streaming",
  );
  const isThinking = status === "streaming" && !hasStreamingAssistant;

  useEffect(() => {
    if (status !== "streaming") return;
    activityAnchor.current?.scrollIntoView?.({ block: "nearest" });
  }, [messages.length, status]);

  return (
    <div aria-busy={status === "streaming"} data-agent-conversation="">
      <ol aria-live="polite" aria-relevant="additions text">
        {messages.map((message) => (
          <ConversationMessage key={message.id} message={message} />
        ))}
        {isThinking ? <ConversationThinking /> : null}
        <li ref={activityAnchor} aria-hidden="true" data-agent-activity-anchor="" />
        <li data-agent-experience="">
          <div data-agent-surface="">{activeSurface}</div>
        </li>
      </ol>
    </div>
  );
}

function ConversationMessage({
  message,
}: {
  message: AgentConversationMessage;
}) {
  return (
    <li
      data-agent-message={message.role}
      data-agent-message-status={message.status}
    >
      <article>
        <header>{message.role === "user" ? "You" : "Buyer assistant"}</header>
        <p>{message.content}</p>
        {message.status === "streaming" ? (
          <ThinkingDots label="Assistant is responding" />
        ) : null}
      </article>
    </li>
  );
}

function ConversationThinking() {
  return (
    <li data-agent-message="assistant" data-agent-message-status="thinking">
      <article>
        <header>Buyer assistant</header>
        <ThinkingDots label="Buyer assistant is thinking" />
      </article>
    </li>
  );
}

function ThinkingDots({ label }: { label: string }) {
  return (
    <span role="status" aria-label={label} data-agent-thinking="">
      <span aria-hidden="true" />
      <span aria-hidden="true" />
      <span aria-hidden="true" />
    </span>
  );
}
