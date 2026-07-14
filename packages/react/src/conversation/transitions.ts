import {
  AgentChatError,
  type AgentHistoryTurn,
  type AgentReviewRequired,
  type AgentStreamEvent,
} from "@routedeck/core";
import {
  historyMessage,
  type AgentConversationMessage,
  type AgentStreamStatus,
} from "./state";

type MessageTransition = (
  current: readonly AgentConversationMessage[],
) => AgentConversationMessage[];

export interface AgentStreamUpdatePort {
  updateMessages(transition: MessageTransition): void;
  setStatus(status: AgentStreamStatus): void;
  setReview(review: AgentReviewRequired | null): void;
  synchronizeTo(target: {
    sessionVersion: number;
    projectionVersion: number;
  }): Promise<void>;
}

export async function applyAgentEvent(
  event: AgentStreamEvent,
  requestId: string,
  updates: AgentStreamUpdatePort,
): Promise<boolean> {
  switch (event.type) {
    case "stream_start":
      requireRequestId(event.request_id, requestId);
      return false;
    case "conversation_snapshot":
      updates.updateMessages((current) =>
        mergeConversationSnapshot(current, event.turns, requestId),
      );
      return false;
    case "user_message":
      requireRequestId(event.request_id, requestId);
      updates.updateMessages((current) =>
        upsertMessage(current, {
          id: event.turn_id,
          requestId: event.request_id,
          role: "user",
          content: event.content,
          status: "finalized",
        }),
      );
      return false;
    case "assistant_delta":
      requireRequestId(event.request_id, requestId);
      updates.updateMessages((current) =>
        appendAssistantDelta(current, event.request_id, event.content),
      );
      return false;
    case "assistant_reset":
      requireRequestId(event.request_id, requestId);
      updates.updateMessages((current) =>
        removeStreamingAssistant(current, event.request_id),
      );
      return false;
    case "assistant_end":
      requireRequestId(event.request_id, requestId);
      await updates.synchronizeTo({
        sessionVersion: event.session_version,
        projectionVersion: event.projection_version,
      });
      updates.updateMessages((current) =>
        finalizeAssistant(current, event.request_id, event.turn_id),
      );
      return false;
    case "review_required":
      updates.setReview({
        status: event.status,
        operation_id: event.operation_id,
        review_id: event.review_id,
        expires_at: event.expires_at,
      });
      updates.setStatus("review_required");
      return false;
    case "chat_error":
      updates.updateMessages((current) =>
        removeRequestMessages(current, requestId),
      );
      throw new AgentChatError(event.code, event.message, null, "rejected");
    case "stream_end":
      requireRequestId(event.request_id, requestId);
      if (event.status === "completed") {
        updates.setStatus("idle");
        return true;
      }
      if (event.status === "requires_review") {
        updates.setStatus("review_required");
        return true;
      }
      if (event.status === "turn_interrupted") {
        updates.updateMessages((current) =>
          removeRequestMessages(current, requestId),
        );
        throw new AgentChatError(
          "chat_turn_interrupted",
          "The buyer-agent turn was interrupted before it was committed.",
          null,
          "interrupted",
        );
      }
      if (event.status === "outcome_unknown") {
        updates.updateMessages((current) =>
          removeRequestMessages(current, requestId),
        );
        throw new AgentChatError(
          "chat_turn_outcome_unknown",
          "The buyer-agent turn could not be durably resolved. Retry the exact message or resynchronize before continuing.",
          null,
          "unknown",
        );
      }
      return false;
  }
}

export function removeRequestMessages(
  messages: readonly AgentConversationMessage[],
  requestId: string,
): AgentConversationMessage[] {
  return messages.filter((message) => message.requestId !== requestId);
}

function removeStreamingAssistant(
  messages: readonly AgentConversationMessage[],
  requestId: string,
): AgentConversationMessage[] {
  return messages.filter(
    (message) =>
      message.requestId !== requestId ||
      message.role !== "assistant" ||
      message.status !== "streaming",
  );
}

function mergeConversationSnapshot(
  current: readonly AgentConversationMessage[],
  turns: readonly AgentHistoryTurn[],
  activeRequestId: string,
): AgentConversationMessage[] {
  const restored = turns.map(historyMessage);
  const restoredIds = new Set(restored.map((message) => message.id));
  const restoredActiveRoles = new Set(
    restored
      .filter((message) => message.requestId === activeRequestId)
      .map((message) => message.role),
  );
  return [
    ...restored,
    ...current.filter(
      (message) =>
        message.requestId === activeRequestId &&
        !restoredIds.has(message.id) &&
        !restoredActiveRoles.has(message.role),
    ),
  ];
}

function upsertMessage(
  messages: readonly AgentConversationMessage[],
  message: AgentConversationMessage,
): AgentConversationMessage[] {
  const index = messages.findIndex((candidate) => candidate.id === message.id);
  if (index < 0) return [...messages, message];
  const next = [...messages];
  next[index] = message;
  return next;
}

function appendAssistantDelta(
  messages: readonly AgentConversationMessage[],
  requestId: string,
  content: string,
): AgentConversationMessage[] {
  const index = messages.findIndex(
    (message) =>
      message.role === "assistant" &&
      message.requestId === requestId &&
      message.status === "streaming",
  );
  if (index < 0) {
    return [
      ...messages,
      {
        id: `assistant:${requestId}`,
        requestId,
        role: "assistant",
        content,
        status: "streaming",
      },
    ];
  }
  const next = [...messages];
  const current = next[index]!;
  next[index] = { ...current, content: current.content + content };
  return next;
}

function finalizeAssistant(
  messages: readonly AgentConversationMessage[],
  requestId: string,
  turnId: string,
): AgentConversationMessage[] {
  const matchingIndices = messages.flatMap((message, index) =>
    message.role === "assistant" && message.requestId === requestId
      ? [index]
      : [],
  );
  const index =
    matchingIndices.find((candidate) => messages[candidate]!.id === turnId) ??
    matchingIndices.find(
      (candidate) => messages[candidate]!.status === "streaming",
    ) ??
    matchingIndices[0];
  if (index === undefined) {
    throw new AgentChatError(
      "assistant_stream_missing",
      "The assistant completion has no streamed message.",
    );
  }
  const finalized = {
    ...messages[index]!,
    id: turnId,
    status: "finalized" as const,
  };
  return messages.flatMap((message, candidate) => {
    const sameAssistant =
      message.role === "assistant" && message.requestId === requestId;
    return sameAssistant ? (candidate === index ? [finalized] : []) : [message];
  });
}

function requireRequestId(actual: string, expected: string): void {
  if (actual !== expected) {
    throw new AgentChatError(
      "chat_request_identity_mismatch",
      "The buyer-agent stream event does not match the active request.",
    );
  }
}
