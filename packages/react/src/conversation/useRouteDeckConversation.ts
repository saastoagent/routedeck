import { useCallback, useEffect, useRef } from "react";

import {
  AgentChatError,
  type AgentChatRequest,
  type AgentChatClient,
  type AgentHistoryTurn,
  type AgentReviewRequired,
  type ConversationRunClient,
  type ConversationRunSnapshot,
} from "@routedeck/core";
import {
  useConversationPresentation,
  type AgentConversationMessage,
  type AgentPendingRequest,
  type AgentStreamStatus,
} from "./presentation";

export interface UseRouteDeckConversationOptions {
  client: AgentChatClient & Partial<ConversationRunClient>;
  initialConversation?: readonly AgentHistoryTurn[];
  sessionVersion: number | null;
  createRequestId(): string;
  synchronizeTo(target: {
    sessionVersion: number;
    projectionVersion: number;
  }): Promise<void>;
  resync(): Promise<void>;
  activeRunRequestId?: string | null;
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
  activeRunRequestId = null,
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

  useEffect(() => {
    if (activeRunRequestId === null || abortRef.current !== null) return;
    const requestId = activeRunRequestId;
    const abort = new AbortController();
    abortRef.current = abort;
    actions.beginTurn();
    void resumeActiveRun().catch((caught: unknown) => {
      if (abort.signal.aborted) return;
      const error = caught instanceof AgentChatError
        ? caught
        : new AgentChatError(
            "conversation_run_resume_failed",
            "The active conversation run could not be restored.",
          );
      actions.failTurn(error, null);
    }).finally(() => {
      if (abortRef.current === abort) abortRef.current = null;
    });

    async function resumeActiveRun(): Promise<void> {
      const loadConversation = client.loadConversation;
      const loadConversationRun = client.loadConversationRun;
      const streamConversationRunEvents = client.streamConversationRunEvents;
      if (
        loadConversation === undefined ||
        loadConversationRun === undefined ||
        streamConversationRunEvents === undefined
      ) {
        throw new AgentChatError(
          "conversation_run_client_unavailable",
          "The configured conversation client cannot restore an active run.",
        );
      }
      const history = await loadConversation(abort.signal);
      actions.restoreSnapshot(history, requestId);
      let run = await loadConversationRun(requestId, abort.signal);
      let content = "";
      content = applyRunProgress(actions, run, content);
      let reconnects = 0;
      while (!isTerminalRun(run)) {
        try {
          for await (const event of streamConversationRunEvents(
            requestId,
            run.cursor,
            abort.signal,
          )) {
            requireRunCursor(event, run);
            run = event;
            reconnects = 0;
            content = applyRunProgress(actions, run, content);
          }
          if (!isTerminalRun(run)) {
            const loaded = await loadConversationRun(requestId, abort.signal);
            requireRunCursor(loaded, run, true);
            run = loaded;
            content = applyRunProgress(actions, run, content);
          }
          if (!isTerminalRun(run)) {
            throw new AgentChatError(
              "conversation_run_stream_incomplete",
              "The active conversation run stream ended before a durable result.",
              null,
              "unknown",
            );
          }
        } catch (caught) {
          if (abort.signal.aborted || !retryableRunTransport(caught)) throw caught;
          const delay = ACTIVE_RUN_RECONNECT_DELAYS_MS[
            Math.min(reconnects, ACTIVE_RUN_RECONNECT_DELAYS_MS.length - 1)
          ]!;
          reconnects += 1;
          await waitForReconnect(delay, abort.signal);
        }
      }
      await finishRun(actions, run, synchronizeTo);
    }

    return () => {
      abort.abort();
      if (abortRef.current === abort) abortRef.current = null;
    };
  }, [activeRunRequestId, actions, client, synchronizeTo]);

  const execute = useCallback(
    async (request: Readonly<AgentChatRequest>) => {
      if (abortRef.current !== null) {
        throw new AgentChatError(
          "chat_turn_in_progress",
          "An agent turn is already in progress.",
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
                  "The agent turn was interrupted before it was committed.",
                  null,
                  "interrupted",
                );
              }
              throw new AgentChatError(
                "chat_turn_outcome_unknown",
                "The agent turn could not be durably resolved. Retry the exact message or resynchronize before continuing.",
                null,
                "unknown",
              );
          }
        }
        if (abort.signal.aborted) {
          throw new AgentChatError(
            "chat_turn_cancelled",
            "The agent turn was cancelled.",
            null,
            "interrupted",
          );
        }
        if (!streamEnded) {
          throw new AgentChatError(
            "chat_stream_incomplete",
            "The agent stream ended without a terminal event.",
          );
        }
        retainedRef.current = null;
        actions.clearFailure();
      } catch (caught) {
        if (abort.signal.aborted) {
          actions.removeRequest(request.request_id);
          const cancellation = new AgentChatError(
            "chat_turn_outcome_unknown",
            "The response was stopped, but the agent turn may already be committed. Retry the exact message or resynchronize before continuing.",
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
                "The agent stream failed.",
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
        "An in-flight agent turn cannot be discarded.",
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

function applyRunProgress(
  actions: ReturnType<typeof useConversationPresentation>["actions"],
  run: ConversationRunSnapshot,
  previous: string,
): string {
  if (run.user_message !== null && run.user_turn_id !== null) {
    actions.showUserMessage({
      type: "user_message",
      content: run.user_message,
      request_id: run.request_id,
      turn_id: run.user_turn_id,
    });
  }
  if (run.assistant_content === previous) return previous;
  if (!run.assistant_content.startsWith(previous)) {
    actions.resetAssistantText(run.request_id);
    if (run.assistant_content) {
      actions.appendAssistantText(run.request_id, run.assistant_content);
    }
    return run.assistant_content;
  }
  const delta = run.assistant_content.slice(previous.length);
  if (delta) actions.appendAssistantText(run.request_id, delta);
  return run.assistant_content;
}

async function finishRun(
  actions: ReturnType<typeof useConversationPresentation>["actions"],
  run: ConversationRunSnapshot,
  synchronizeTo: UseRouteDeckConversationOptions["synchronizeTo"],
): Promise<void> {
  if (run.stage === "interrupted") {
    throw new AgentChatError(
      run.failure?.code ?? "chat_turn_interrupted",
      run.failure?.message ?? "The agent turn was interrupted.",
      null,
      "interrupted",
    );
  }
  if (
    run.stage !== "completed" ||
    run.session_version === null ||
    run.projection_version === null
  ) {
    throw new AgentChatError(
      "conversation_run_incomplete",
      "The active conversation run ended without a durable result.",
    );
  }
  await synchronizeTo({
    sessionVersion: run.session_version,
    projectionVersion: run.projection_version,
  });
  if (run.review !== null) {
    actions.requireReview(run.review);
    actions.completeTurn("review_required");
    return;
  }
  if (run.turn_id === null) {
    throw new AgentChatError(
      "conversation_run_completion_invalid",
      "The completed conversation run has no assistant turn.",
    );
  }
  actions.finalizeAssistant(run.request_id, run.turn_id);
  actions.completeTurn("idle");
  actions.clearFailure();
}

function isTerminalRun(run: ConversationRunSnapshot): boolean {
  return run.stage === "completed" || run.stage === "interrupted";
}

const ACTIVE_RUN_RECONNECT_DELAYS_MS = [100, 250, 500] as const;

function requireRunCursor(
  next: ConversationRunSnapshot,
  previous: ConversationRunSnapshot,
  allowEqual = false,
): void {
  requireRequestId(next.request_id, previous.request_id);
  if (next.cursor < previous.cursor || (!allowEqual && next.cursor === previous.cursor)) {
    throw new AgentChatError(
      "conversation_run_cursor_regressed",
      "The active conversation run cursor did not advance.",
    );
  }
}

function retryableRunTransport(error: unknown): boolean {
  if (!(error instanceof AgentChatError)) return true;
  return (
    error.code === "conversation_run_stream_incomplete" ||
    error.code === "conversation_run_stream_body_missing" ||
    (error.status !== null && error.status >= 500)
  );
}

async function waitForReconnect(
  milliseconds: number,
  signal: AbortSignal,
): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(signal.reason);
      return;
    }
    const timer = globalThis.setTimeout(done, milliseconds);
    signal.addEventListener("abort", aborted, { once: true });

    function done(): void {
      signal.removeEventListener("abort", aborted);
      resolve();
    }

    function aborted(): void {
      globalThis.clearTimeout(timer);
      reject(signal.reason);
    }
  });
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
      "The agent stream event does not match the active request.",
    );
  }
}
