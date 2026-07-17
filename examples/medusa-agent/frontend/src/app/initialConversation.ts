import {
  AgentChatError,
  type AgentHistoryTurn,
  type RouteDeckAgentClient,
  type RouteDeckClientState,
  type RouteDeckStore,
} from "@routedeck/core";

export const INITIAL_GREETING_REQUEST_ID = "medusa.initial-greeting.v1";

const GREETING_CONVERGENCE_TIMEOUT_MS = 120_000;
const GREETING_CONFLICT_CODES = new Set([
  "operation_in_progress",
  "version_conflict",
]);

export interface InitialConversationRouteDeck {
  store: Pick<
    RouteDeckStore,
    "getState" | "subscribe" | "resync" | "synchronizeTo"
  >;
}

export interface InitialConversationOptions {
  requestId?: string;
}

export async function loadInitialConversation(
  routeDeck: InitialConversationRouteDeck,
  chatClient: RouteDeckAgentClient,
  options: InitialConversationOptions = {},
): Promise<readonly AgentHistoryTurn[]> {
  const existing = await chatClient.loadConversation();
  if (existing.length > 0) return existing;

  const sessionVersion = routeDeck.store.getState().sessionVersion;
  if (sessionVersion === null) {
    throw new AgentChatError(
      "routedeck_session_unavailable",
      "The RouteDeck session is unavailable for the buyer greeting.",
    );
  }
  const requestId = options.requestId ?? INITIAL_GREETING_REQUEST_ID;
  try {
    return await runGreeting(
      routeDeck.store,
      chatClient,
      requestId,
      sessionVersion,
    );
  } catch (error) {
    if (!isGreetingConflict(error)) throw error;
    return convergeWithWinningGreeting(routeDeck.store, chatClient, requestId);
  }
}

export function createGreetingRetryRequestId(): string {
  const identifier = globalThis.crypto.randomUUID();
  if (!identifier) {
    throw new AgentChatError(
      "entry_request_id_unavailable",
      "The browser could not create a buyer greeting retry ID.",
    );
  }
  return `${INITIAL_GREETING_REQUEST_ID}.retry.${identifier}`;
}

async function runGreeting(
  store: Pick<RouteDeckStore, "synchronizeTo">,
  chatClient: RouteDeckAgentClient,
  requestId: string,
  sessionVersion: number,
): Promise<readonly AgentHistoryTurn[]> {
  let completedVersions:
    | { sessionVersion: number; projectionVersion: number }
    | null = null;
  let streamCompleted = false;
  for await (const event of chatClient.streamAssistantTurn({
    request_id: requestId,
    expected_session_version: sessionVersion,
  })) {
    if (streamCompleted) {
      throw assistantTurnFailure(
        "assistant_turn_event_after_end",
        "The buyer greeting emitted an event after its terminal frame.",
      );
    }
    switch (event.type) {
      case "stream_start":
        requireAssistantRequestId(event.request_id, requestId);
        break;
      case "conversation_snapshot":
        break;
      case "assistant_delta":
      case "assistant_reset":
        requireAssistantRequestId(event.request_id, requestId);
        break;
      case "assistant_end":
        requireAssistantRequestId(event.request_id, requestId);
        if (completedVersions !== null) {
          throw assistantTurnFailure(
            "assistant_turn_completion_duplicate",
            "The buyer greeting emitted more than one assistant completion.",
          );
        }
        completedVersions = {
          sessionVersion: event.session_version,
          projectionVersion: event.projection_version,
        };
        break;
      case "stream_end":
        requireAssistantRequestId(event.request_id, requestId);
        if (event.status !== "completed") {
          throw assistantTurnFailure(
            "assistant_turn_not_completed",
            "The buyer greeting did not complete successfully.",
          );
        }
        streamCompleted = true;
        break;
      case "chat_error":
        throw new AgentChatError(event.code, event.message, null, "rejected");
      case "user_message":
        throw assistantTurnFailure(
          "assistant_turn_user_message_forbidden",
          "The buyer greeting emitted an unexpected user message.",
        );
      case "review_required":
        throw assistantTurnFailure(
          "assistant_turn_review_forbidden",
          "The buyer greeting unexpectedly requested review.",
        );
    }
  }
  if (!streamCompleted || completedVersions === null) {
    throw assistantTurnFailure(
      "assistant_turn_stream_incomplete",
      "The buyer greeting ended without a durable assistant completion.",
    );
  }
  await store.synchronizeTo(completedVersions);
  return chatClient.loadConversation();
}

async function convergeWithWinningGreeting(
  store: Pick<
    RouteDeckStore,
    "getState" | "subscribe" | "resync" | "synchronizeTo"
  >,
  chatClient: RouteDeckAgentClient,
  requestId: string,
): Promise<readonly AgentHistoryTurn[]> {
  await store.resync();
  const alreadyCommitted = await chatClient.loadConversation();
  if (alreadyCommitted.length > 0) return alreadyCommitted;

  const terminal = await waitForGreetingTerminal(store, requestId);
  if (terminal.projection_version === null) {
    throw assistantTurnFailure(
      "initial_greeting_projection_unavailable",
      "The completed buyer greeting did not publish a projection version.",
    );
  }
  await store.synchronizeTo({
    sessionVersion: terminal.session_version,
    projectionVersion: terminal.projection_version,
  });
  if (terminal.event_type === "turn_interrupted") {
    throw new AgentChatError(
      terminal.payload.failure?.code ?? "initial_greeting_interrupted",
      terminal.payload.failure?.public_message ??
        "The buyer greeting was interrupted. Retry it explicitly to continue.",
      null,
      "interrupted",
    );
  }
  const conversation = await chatClient.loadConversation();
  if (conversation.length === 0) {
    throw assistantTurnFailure(
      "initial_greeting_not_committed",
      "The buyer greeting completed without a durable conversation turn.",
    );
  }
  return conversation;
}

function waitForGreetingTerminal(
  store: Pick<RouteDeckStore, "getState" | "subscribe">,
  requestId: string,
): Promise<NonNullable<RouteDeckClientState["lastEvent"]>> {
  const current = greetingTerminal(store.getState(), requestId);
  if (current !== null) return Promise.resolve(current);
  requireGreetingInProgress(store.getState(), requestId);

  return new Promise((resolve, reject) => {
    let settled = false;
    let timeout: ReturnType<typeof globalThis.setTimeout> | null = null;
    let unsubscribe: () => void = () => undefined;
    const finish = (
      result:
        | { event: NonNullable<RouteDeckClientState["lastEvent"]> }
        | { error: AgentChatError },
    ) => {
      if (settled) return;
      settled = true;
      if (timeout !== null) globalThis.clearTimeout(timeout);
      unsubscribe();
      if ("event" in result) resolve(result.event);
      else reject(result.error);
    };
    const observe = () => {
      const state = store.getState();
      const terminal = greetingTerminal(state, requestId);
      if (terminal !== null) {
        finish({ event: terminal });
        return;
      }
      if (state.syncStatus === "error" || state.syncStatus === "disposed") {
        finish({
          error: assistantTurnFailure(
            "initial_greeting_convergence_failed",
            state.error?.message ??
              "RouteDeck could not observe the active buyer greeting.",
          ),
        });
        return;
      }
      if (
        state.projection?.interaction.phase === "idle" &&
        state.lastEvent?.payload.request_id !== requestId
      ) {
        finish({
          error: assistantTurnFailure(
            "initial_greeting_convergence_lost",
            "The active buyer greeting ended without its terminal event.",
          ),
        });
      }
    };
    unsubscribe = store.subscribe(observe);
    observe();
    if (settled) return;
    timeout = globalThis.setTimeout(
      () =>
        finish({
          error: assistantTurnFailure(
            "initial_greeting_convergence_timeout",
            "The active buyer greeting did not finish in time.",
          ),
        }),
      GREETING_CONVERGENCE_TIMEOUT_MS,
    );
  });
}

function greetingTerminal(
  state: RouteDeckClientState,
  requestId: string,
): NonNullable<RouteDeckClientState["lastEvent"]> | null {
  const event = state.lastEvent;
  return event !== null &&
    event.payload.request_id === requestId &&
    (event.event_type === "turn_finalized" ||
      event.event_type === "turn_interrupted")
    ? event
    : null;
}

function requireGreetingInProgress(
  state: RouteDeckClientState,
  requestId: string,
): void {
  const activeChat =
    state.projection?.interaction.phase === "active" &&
    state.projection.interaction.owner === "chat";
  const greetingStarted =
    state.lastEvent?.event_type === "turn_started" &&
    state.lastEvent.payload.request_id === requestId;
  if (!activeChat && !greetingStarted) {
    throw assistantTurnFailure(
      "initial_greeting_convergence_unavailable",
      "No active buyer greeting is available to restore.",
    );
  }
}

function isGreetingConflict(error: unknown): error is AgentChatError {
  return (
    error instanceof AgentChatError &&
    GREETING_CONFLICT_CODES.has(error.code)
  );
}

function requireAssistantRequestId(actual: string, expected: string): void {
  if (actual !== expected) {
    throw assistantTurnFailure(
      "assistant_turn_request_identity_mismatch",
      "The buyer greeting stream does not match the active request.",
    );
  }
}

function assistantTurnFailure(code: string, message: string): AgentChatError {
  return new AgentChatError(code, message, null, "unknown");
}
