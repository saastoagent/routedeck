import type { ReactNode } from "react";

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
  return (
    <div aria-busy={status === "streaming"} data-agent-conversation="">
      <ol aria-live="polite" aria-relevant="additions text">
        {messages.map((message) => (
          <ConversationMessage key={message.id} message={message} />
        ))}
        <li data-agent-surface="">{activeSurface}</li>
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
          <span aria-label="Assistant is responding">...</span>
        ) : null}
      </article>
    </li>
  );
}
