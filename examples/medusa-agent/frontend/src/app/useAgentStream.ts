import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  AgentChatError,
  type AgentChatRequest,
  type AgentChatClient,
  type AgentHistoryTurn,
  type AgentReviewRequired,
} from "./chatClient";
import {
  historyMessage,
  pendingRequestFor,
  type AgentConversationMessage,
  type AgentPendingRequest,
  type AgentStreamStatus,
} from "./agentStreamState";
import {
  applyAgentEvent,
  removeRequestMessages,
} from "./agentStreamTransitions";

export type {
  AgentConversationMessage,
  AgentPendingRequest,
  AgentStreamStatus,
} from "./agentStreamState";

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
              {
                updateMessages: setMessages,
                setStatus,
                setReview,
                synchronizeTo,
              },
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
