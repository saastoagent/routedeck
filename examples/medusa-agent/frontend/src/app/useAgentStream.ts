import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";

import {
  AgentChatError,
  type AgentChatRequest,
  type AgentChatClient,
  type AgentHistoryTurn,
  type AgentReviewRequired,
  type AgentStreamEvent,
} from "./chatClient";

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

export interface UseAgentStreamOptions {
  client: AgentChatClient;
  initialConversation?: readonly AgentHistoryTurn[];
  sessionVersion: number | null;
  createRequestId(): string;
  synchronizeTo(target: {
    sessionVersion: number;
    projectionVersion: number;
  }): Promise<void>;
  resync(): Promise<void>;
}

export interface AgentPendingRequest {
  readonly requestId: string;
  readonly expectedSessionVersion: number;
  readonly message: string;
}

export interface AgentStreamState {
  messages: readonly AgentConversationMessage[];
  status: AgentStreamStatus;
  error: AgentChatError | null;
  review: AgentReviewRequired | null;
  pendingRequest: AgentPendingRequest | null;
  send(message: string): Promise<void>;
  retry(): Promise<void>;
  discardPending(): Promise<void>;
  cancel(): void;
}

export function useAgentStream({
  client,
  initialConversation = [],
  sessionVersion,
  createRequestId,
  synchronizeTo,
  resync,
}: UseAgentStreamOptions): AgentStreamState {
  const [messages, setMessages] = useState<AgentConversationMessage[]>(() =>
    initialConversation.map(historyMessage),
  );
  const [status, setStatus] = useState<AgentStreamStatus>("idle");
  const [error, setError] = useState<AgentChatError | null>(null);
  const [review, setReview] = useState<AgentReviewRequired | null>(null);
  const [pendingRequest, setPendingRequest] = useState<AgentPendingRequest | null>(
    null,
  );
  const abortRef = useRef<AbortController | null>(null);
  const retainedRef = useRef<Readonly<AgentChatRequest> | null>(null);

  useEffect(
    () => () => {
      abortRef.current?.abort();
      abortRef.current = null;
    },
    [],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const execute = useCallback(
    async (request: Readonly<AgentChatRequest>) => {
      if (abortRef.current !== null) {
        throw new AgentChatError(
          "chat_turn_in_progress",
          "A buyer-agent turn is already in progress.",
        );
      }
      const abort = new AbortController();
      abortRef.current = abort;
      setStatus("streaming");
      setError(null);
      setReview(null);
      let streamEnded = false;
      try {
        for await (const event of client.stream(
          request,
          abort.signal,
        )) {
          streamEnded =
            (await applyAgentEvent(
              event,
              request.request_id,
              synchronizeTo,
              setMessages,
              setStatus,
              setReview,
            )) || streamEnded;
        }
        if (abort.signal.aborted) {
          throw new AgentChatError(
            "chat_turn_cancelled",
            "The buyer-agent turn was cancelled.",
            null,
            "interrupted",
          );
        }
        if (!streamEnded) {
          throw new AgentChatError(
            "chat_stream_incomplete",
            "The buyer-agent stream ended without a terminal event.",
          );
        }
        retainedRef.current = null;
        setPendingRequest(null);
      } catch (caught) {
        if (abort.signal.aborted) {
          setMessages((current) =>
            removeRequestMessages(current, request.request_id),
          );
          const cancellation = new AgentChatError(
            "chat_turn_outcome_unknown",
            "The response was stopped, but the buyer-agent turn may already be committed. Retry the exact message or resynchronize before continuing.",
            null,
            "unknown",
          );
          retainedRef.current = request;
          setPendingRequest(pendingRequestFor(request));
          setStatus("error");
          setError(cancellation);
          throw cancellation;
        }
        const nextError =
          caught instanceof AgentChatError
            ? caught
            : new AgentChatError(
                "chat_stream_failed",
                "The buyer-agent stream failed.",
              );
        if (nextError.outcome === "unknown") {
          retainedRef.current = request;
          setPendingRequest(pendingRequestFor(request));
        } else {
          retainedRef.current = null;
          setPendingRequest(null);
        }
        setError(nextError);
        setStatus("error");
        throw nextError;
      } finally {
        if (abortRef.current === abort) abortRef.current = null;
      }
    },
    [client, synchronizeTo],
  );

  const send = useCallback(
    async (message: string) => {
      if (retainedRef.current !== null) {
        throw new AgentChatError(
          "chat_retry_required",
          "Retry or discard the outcome-unknown chat request before sending another message.",
          null,
          "not_sent",
        );
      }
      if (sessionVersion === null) {
        throw new AgentChatError(
          "session_not_ready",
          "The RouteDeck session is not ready for chat.",
          null,
          "not_sent",
        );
      }
      if (!message.trim()) {
        throw new AgentChatError(
          "message_empty",
          "A chat message must contain text.",
          null,
          "not_sent",
        );
      }
      await execute(
        Object.freeze({
          request_id: createRequestId(),
          expected_session_version: sessionVersion,
          message,
        }),
      );
    },
    [createRequestId, execute, sessionVersion],
  );

  const retry = useCallback(async () => {
    const retained = retainedRef.current;
    if (retained === null) {
      throw new AgentChatError(
        "chat_retry_missing",
        "There is no outcome-unknown chat request to retry.",
        null,
        "not_sent",
      );
    }
    await execute(retained);
  }, [execute]);

  const discardPending = useCallback(async () => {
    if (abortRef.current !== null) {
      throw new AgentChatError(
        "chat_turn_in_progress",
        "An in-flight buyer-agent turn cannot be discarded.",
        null,
        "not_sent",
      );
    }
    if (retainedRef.current === null) {
      throw new AgentChatError(
        "chat_retry_missing",
        "There is no outcome-unknown chat request to discard.",
        null,
        "not_sent",
      );
    }
    try {
      await resync();
      retainedRef.current = null;
      setPendingRequest(null);
      setError(null);
      setStatus("idle");
    } catch (caught) {
      const nextError =
        caught instanceof AgentChatError
          ? caught
          : new AgentChatError(
              "chat_resync_failed",
              "RouteDeck could not resynchronize the outcome-unknown chat request.",
            );
      setError(nextError);
      setStatus("error");
      throw nextError;
    }
  }, [resync]);

  return {
    messages,
    status,
    error,
    review,
    pendingRequest,
    send,
    retry,
    discardPending,
    cancel,
  };
}

type MessagesSetter = Dispatch<SetStateAction<AgentConversationMessage[]>>;
type StatusSetter = Dispatch<SetStateAction<AgentStreamStatus>>;
type ReviewSetter = Dispatch<SetStateAction<AgentReviewRequired | null>>;

async function applyAgentEvent(
  event: AgentStreamEvent,
  requestId: string,
  synchronizeTo: UseAgentStreamOptions["synchronizeTo"],
  setMessages: MessagesSetter,
  setStatus: StatusSetter,
  setReview: ReviewSetter,
): Promise<boolean> {
  switch (event.type) {
    case "stream_start":
      requireRequestId(event.request_id, requestId);
      return false;
    case "conversation_snapshot":
      setMessages((current) =>
        mergeConversationSnapshot(current, event.turns, requestId),
      );
      return false;
    case "user_message":
      requireRequestId(event.request_id, requestId);
      setMessages((current) =>
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
      setMessages((current) =>
        appendAssistantDelta(current, event.request_id, event.content),
      );
      return false;
    case "assistant_end":
      requireRequestId(event.request_id, requestId);
      await synchronizeTo({
        sessionVersion: event.session_version,
        projectionVersion: event.projection_version,
      });
      setMessages((current) =>
        finalizeAssistant(current, event.request_id, event.turn_id),
      );
      return false;
    case "review_required":
      setReview({
        status: event.status,
        operation_id: event.operation_id,
        review_id: event.review_id,
        expires_at: event.expires_at,
      });
      setStatus("review_required");
      return false;
    case "chat_error":
      setMessages((current) =>
        removeRequestMessages(current, requestId),
      );
      throw new AgentChatError(event.code, event.message, null, "rejected");
    case "stream_end":
      requireRequestId(event.request_id, requestId);
      if (event.status === "completed") {
        setStatus("idle");
        return true;
      }
      if (event.status === "requires_review") {
        setStatus("review_required");
        return true;
      }
      if (event.status === "turn_interrupted") {
        setMessages((current) =>
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
        setMessages((current) =>
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

function historyMessage(turn: AgentHistoryTurn): AgentConversationMessage {
  return {
    id: turn.turn_id,
    requestId: turn.request_id,
    role: turn.role,
    content: turn.content,
    status: "finalized",
  };
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

function removeRequestMessages(
  messages: readonly AgentConversationMessage[],
  requestId: string,
): AgentConversationMessage[] {
  return messages.filter((message) => message.requestId !== requestId);
}

function requireRequestId(actual: string, expected: string): void {
  if (actual !== expected) {
    throw new AgentChatError(
      "chat_request_identity_mismatch",
      "The buyer-agent stream event does not match the active request.",
    );
  }
}

function pendingRequestFor(
  request: Readonly<AgentChatRequest>,
): AgentPendingRequest {
  return Object.freeze({
    requestId: request.request_id,
    expectedSessionVersion: request.expected_session_version,
    message: request.message,
  });
}
