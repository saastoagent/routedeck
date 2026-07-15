import { useCallback, useEffect, useRef } from "react";

import {
  AgentChatError,
  type AgentChatRequest,
  type AgentChatClient,
  type AgentHistoryTurn,
  type AgentReviewRequired,
} from "@routedeck/core";
import {
  useConversationPresentation,
  type AgentConversationMessage,
  type AgentPendingRequest,
  type AgentStreamStatus,
} from "./presentation";

export interface UseRouteDeckConversationOptions {
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

export function useRouteDeckConversation({
  client,
  initialConversation = [],
  sessionVersion,
  createRequestId,
  synchronizeTo,
  resync,
}: UseRouteDeckConversationOptions): AgentStreamState {
  const presentation = useConversationPresentation(initialConversation);
  const actions = presentation.actions;
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
      actions.beginTurn();
      let streamEnded = false;
      try {
        for await (const event of client.stream(request, abort.signal)) {
          switch (event.type) {
            case "stream_start":
              requireRequestId(event.request_id, request.request_id);
              break;
            case "conversation_snapshot":
              actions.restoreSnapshot(event.turns, request.request_id);
              break;
            case "user_message":
              requireRequestId(event.request_id, request.request_id);
              actions.showUserMessage(event);
              break;
            case "assistant_delta":
              requireRequestId(event.request_id, request.request_id);
              actions.appendAssistantText(event.request_id, event.content);
              break;
            case "assistant_reset":
              requireRequestId(event.request_id, request.request_id);
              actions.resetAssistantText(event.request_id);
              break;
            case "assistant_end":
              requireRequestId(event.request_id, request.request_id);
              await synchronizeTo({
                sessionVersion: event.session_version,
                projectionVersion: event.projection_version,
              });
              actions.finalizeAssistant(event.request_id, event.turn_id);
              break;
            case "review_required":
              actions.requireReview({
                status: event.status,
                operation_id: event.operation_id,
                review_id: event.review_id,
                expires_at: event.expires_at,
              });
              break;
            case "chat_error":
              actions.removeRequest(request.request_id);
              throw new AgentChatError(
                event.code,
                event.message,
                null,
                "rejected",
              );
            case "stream_end":
              requireRequestId(event.request_id, request.request_id);
              if (event.status === "completed") {
                actions.completeTurn("idle");
                streamEnded = true;
                break;
              }
              if (event.status === "requires_review") {
                actions.completeTurn("review_required");
                streamEnded = true;
                break;
              }
              actions.removeRequest(request.request_id);
              if (event.status === "turn_interrupted") {
                throw new AgentChatError(
                  "chat_turn_interrupted",
                  "The buyer-agent turn was interrupted before it was committed.",
                  null,
                  "interrupted",
                );
              }
              throw new AgentChatError(
                "chat_turn_outcome_unknown",
                "The buyer-agent turn could not be durably resolved. Retry the exact message or resynchronize before continuing.",
                null,
                "unknown",
              );
          }
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
        actions.clearFailure();
      } catch (caught) {
        if (abort.signal.aborted) {
          actions.removeRequest(request.request_id);
          const cancellation = new AgentChatError(
            "chat_turn_outcome_unknown",
            "The response was stopped, but the buyer-agent turn may already be committed. Retry the exact message or resynchronize before continuing.",
            null,
            "unknown",
          );
          retainedRef.current = request;
          actions.failTurn(cancellation, pendingRequestFor(request));
          throw cancellation;
        }
        const nextError =
          caught instanceof AgentChatError
            ? caught
            : new AgentChatError(
                "chat_stream_failed",
                "The buyer-agent stream failed.",
              );
        const pending =
          nextError.outcome === "unknown" ? pendingRequestFor(request) : null;
        retainedRef.current = pending === null ? null : request;
        actions.failTurn(nextError, pending);
        throw nextError;
      } finally {
        if (abortRef.current === abort) abortRef.current = null;
      }
    },
    [actions, client, synchronizeTo],
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
    const retained = retainedRef.current;
    if (retained === null) {
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
      actions.clearFailure();
      actions.completeTurn("idle");
    } catch (caught) {
      const nextError =
        caught instanceof AgentChatError
          ? caught
          : new AgentChatError(
              "chat_resync_failed",
              "RouteDeck could not resynchronize the outcome-unknown chat request.",
            );
      actions.failTurn(nextError, pendingRequestFor(retained));
      throw nextError;
    }
  }, [actions, resync]);

  return {
    ...presentation.state,
    send,
    retry,
    discardPending,
    cancel,
  };
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

function requireRequestId(actual: string, expected: string): void {
  if (actual !== expected) {
    throw new AgentChatError(
      "chat_request_identity_mismatch",
      "The buyer-agent stream event does not match the active request.",
    );
  }
}
