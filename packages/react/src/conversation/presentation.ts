import { useCallback, useMemo, useState } from "react";

import {
  AgentChatError,
  type AgentHistoryTurn,
  type AgentReviewRequired,
  type AgentStreamEvent,
} from "@routedeck/core";

export interface AgentConversationMessage {
  id: string;
  requestId: string | null;
  role: "user" | "assistant";
  content: string;
  status: "finalized" | "streaming";
}

export type AgentStreamStatus =
  | "idle"
  | "streaming"
  | "review_required"
  | "error";

export interface AgentPendingRequest {
  readonly requestId: string;
  readonly expectedSessionVersion: number;
  readonly message: string;
}

export interface ConversationPresentationState {
  readonly messages: readonly AgentConversationMessage[];
  readonly status: AgentStreamStatus;
  readonly error: AgentChatError | null;
  readonly review: AgentReviewRequired | null;
  readonly pendingRequest: AgentPendingRequest | null;
}

export interface ConversationPresentationActions {
  beginTurn(): void;
  restoreSnapshot(
    turns: readonly AgentHistoryTurn[],
    requestId: string,
  ): void;
  showUserMessage(
    event: Extract<AgentStreamEvent, { type: "user_message" }>,
  ): void;
  appendAssistantText(requestId: string, content: string): void;
  resetAssistantText(requestId: string): void;
  finalizeAssistant(requestId: string, turnId: string): void;
  requireReview(review: AgentReviewRequired): void;
  removeRequest(requestId: string): void;
  completeTurn(status: "idle" | "review_required"): void;
  failTurn(
    error: AgentChatError,
    pending: AgentPendingRequest | null,
  ): void;
  clearFailure(): void;
}

export interface ConversationPresentation {
  readonly state: ConversationPresentationState;
  readonly actions: ConversationPresentationActions;
}

export function useConversationPresentation(
  initialConversation: readonly AgentHistoryTurn[],
): ConversationPresentation {
  const [messages, setMessages] = useState<AgentConversationMessage[]>(() =>
    initialConversation.map(historyMessage),
  );
  const [status, setStatus] = useState<AgentStreamStatus>("idle");
  const [error, setError] = useState<AgentChatError | null>(null);
  const [review, setReview] = useState<AgentReviewRequired | null>(null);
  const [pendingRequest, setPendingRequest] =
    useState<AgentPendingRequest | null>(null);

  const beginTurn = useCallback(() => {
    setStatus("streaming");
    setError(null);
    setReview(null);
  }, []);

  const restoreSnapshot = useCallback(
    (turns: readonly AgentHistoryTurn[], requestId: string) => {
      setMessages((current) =>
        mergeConversationSnapshot(current, turns, requestId),
      );
    },
    [],
  );

  const showUserMessage = useCallback(
    (event: Extract<AgentStreamEvent, { type: "user_message" }>) => {
      setMessages((current) =>
        upsertMessage(current, {
          id: event.turn_id,
          requestId: event.request_id,
          role: "user",
          content: event.content,
          status: "finalized",
        }),
      );
    },
    [],
  );

  const appendAssistantText = useCallback(
    (requestId: string, content: string) => {
      setMessages((current) =>
        appendAssistantDelta(current, requestId, content),
      );
    },
    [],
  );

  const resetAssistantText = useCallback((requestId: string) => {
    setMessages((current) =>
      removeStreamingAssistant(current, requestId),
    );
  }, []);

  const finalizeAssistantAction = useCallback(
    (requestId: string, turnId: string) => {
      setMessages((current) =>
        finalizeAssistant(current, requestId, turnId),
      );
    },
    [],
  );

  const requireReview = useCallback((next: AgentReviewRequired) => {
    setReview(next);
    setStatus("review_required");
  }, []);

  const removeRequest = useCallback((requestId: string) => {
    setMessages((current) => removeRequestMessages(current, requestId));
  }, []);

  const completeTurn = useCallback(
    (next: "idle" | "review_required") => setStatus(next),
    [],
  );

  const failTurn = useCallback(
    (nextError: AgentChatError, pending: AgentPendingRequest | null) => {
      setError(nextError);
      setPendingRequest(pending);
      setStatus("error");
    },
    [],
  );

  const clearFailure = useCallback(() => {
    setError(null);
    setPendingRequest(null);
  }, []);

  const actions = useMemo<ConversationPresentationActions>(
    () => ({
      beginTurn,
      restoreSnapshot,
      showUserMessage,
      appendAssistantText,
      resetAssistantText,
      finalizeAssistant: finalizeAssistantAction,
      requireReview,
      removeRequest,
      completeTurn,
      failTurn,
      clearFailure,
    }),
    [
      appendAssistantText,
      beginTurn,
      clearFailure,
      completeTurn,
      failTurn,
      finalizeAssistantAction,
      removeRequest,
      requireReview,
      resetAssistantText,
      restoreSnapshot,
      showUserMessage,
    ],
  );

  return {
    state: { messages, status, error, review, pendingRequest },
    actions,
  };
}

function historyMessage(turn: AgentHistoryTurn): AgentConversationMessage {
  return {
    id: turn.turn_id,
    requestId: turn.request_id,
    role: turn.role,
    content: turn.content,
    status: "finalized",
  };
}

function removeRequestMessages(
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
