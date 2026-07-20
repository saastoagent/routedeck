import type { RouteDeckClientState } from "../store/state";
import type { RouteDeckStore } from "../store/types";
import {
  AgentChatError,
  type AgentHistoryTurn,
  type RouteDeckAgentClient,
} from "./types";

const DEFAULT_CONVERGENCE_TIMEOUT_MS = 120_000;
const CONFLICT_CODES = new Set(["operation_in_progress", "version_conflict"]);

export interface AssistantInitiatedTurnOptions {
  requestId: string;
  convergenceTimeoutMs?: number;
}

type AssistantTurnStore = Pick<
  RouteDeckStore,
  "getState" | "subscribe" | "resync" | "synchronizeTo"
>;

export async function runAssistantInitiatedTurn(
  store: AssistantTurnStore,
  client: RouteDeckAgentClient,
  options: AssistantInitiatedTurnOptions,
): Promise<readonly AgentHistoryTurn[]> {
  const sessionVersion = store.getState().sessionVersion;
  if (sessionVersion === null) {
    throw failure(
      "routedeck_session_unavailable",
      "The RouteDeck session is unavailable for an assistant turn.",
    );
  }
  try {
    return await runTurn(store, client, options.requestId, sessionVersion);
  } catch (error) {
    if (!isConflict(error)) throw error;
    return convergeWithWinningTurn(store, client, options);
  }
}

async function runTurn(
  store: Pick<RouteDeckStore, "synchronizeTo">,
  client: RouteDeckAgentClient,
  requestId: string,
  sessionVersion: number,
): Promise<readonly AgentHistoryTurn[]> {
  let completedVersions:
    | { sessionVersion: number; projectionVersion: number }
    | null = null;
  let streamCompleted = false;
  for await (const event of client.streamAssistantTurn({
    request_id: requestId,
    expected_session_version: sessionVersion,
  })) {
    if (streamCompleted) {
      throw failure(
        "assistant_turn_event_after_end",
        "The assistant turn emitted an event after its terminal frame.",
      );
    }
    switch (event.type) {
      case "stream_start":
        requireRequestId(event.request_id, requestId);
        break;
      case "conversation_snapshot":
        break;
      case "assistant_delta":
      case "assistant_reset":
        requireRequestId(event.request_id, requestId);
        break;
      case "assistant_end":
        requireRequestId(event.request_id, requestId);
        if (completedVersions !== null) {
          throw failure(
            "assistant_turn_completion_duplicate",
            "The assistant turn emitted more than one completion.",
          );
        }
        completedVersions = {
          sessionVersion: event.session_version,
          projectionVersion: event.projection_version,
        };
        break;
      case "stream_end":
        requireRequestId(event.request_id, requestId);
        if (event.status !== "completed") {
          throw failure(
            "assistant_turn_not_completed",
            "The assistant turn did not complete successfully.",
          );
        }
        streamCompleted = true;
        break;
      case "chat_error":
        throw new AgentChatError(event.code, event.message, null, "rejected");
      case "user_message":
        throw failure(
          "assistant_turn_user_message_forbidden",
          "An assistant-initiated turn emitted an unexpected user message.",
        );
      case "review_required":
        throw failure(
          "assistant_turn_review_forbidden",
          "An assistant-initiated turn unexpectedly requested review.",
        );
    }
  }
  if (!streamCompleted || completedVersions === null) {
    throw failure(
      "assistant_turn_stream_incomplete",
      "The assistant turn ended without a durable completion.",
    );
  }
  await store.synchronizeTo(completedVersions);
  return client.loadConversation();
}

async function convergeWithWinningTurn(
  store: AssistantTurnStore,
  client: RouteDeckAgentClient,
  options: AssistantInitiatedTurnOptions,
): Promise<readonly AgentHistoryTurn[]> {
  await store.resync();
  const alreadyCommitted = await client.loadConversation();
  if (alreadyCommitted.length > 0) return alreadyCommitted;

  const terminal = await waitForTerminal(store, options);
  if (terminal.projection_version === null) {
    throw failure(
      "assistant_turn_projection_unavailable",
      "The completed assistant turn did not publish a projection version.",
    );
  }
  await store.synchronizeTo({
    sessionVersion: terminal.session_version,
    projectionVersion: terminal.projection_version,
  });
  if (terminal.event_type === "turn_interrupted") {
    throw new AgentChatError(
      terminal.payload.failure?.code ?? "assistant_turn_interrupted",
      terminal.payload.failure?.public_message ??
        "The assistant turn was interrupted. Retry it explicitly to continue.",
      null,
      "interrupted",
    );
  }
  const conversation = await client.loadConversation();
  if (conversation.length === 0) {
    throw failure(
      "assistant_turn_not_committed",
      "The assistant turn completed without a durable conversation turn.",
    );
  }
  return conversation;
}

function waitForTerminal(
  store: Pick<RouteDeckStore, "getState" | "subscribe">,
  options: AssistantInitiatedTurnOptions,
): Promise<NonNullable<RouteDeckClientState["lastEvent"]>> {
  const current = terminalEvent(store.getState(), options.requestId);
  if (current !== null) return Promise.resolve(current);
  requireTurnInProgress(store.getState(), options.requestId);

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
      const terminal = terminalEvent(state, options.requestId);
      if (terminal !== null) {
        finish({ event: terminal });
        return;
      }
      if (state.syncStatus === "error" || state.syncStatus === "disposed") {
        finish({
          error: failure(
            "assistant_turn_convergence_failed",
            state.error?.message ??
              "RouteDeck could not observe the active assistant turn.",
          ),
        });
        return;
      }
      if (
        state.projection?.interaction.phase === "idle" &&
        state.lastEvent?.payload.request_id !== options.requestId
      ) {
        finish({
          error: failure(
            "assistant_turn_convergence_lost",
            "The active assistant turn ended without its terminal event.",
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
          error: failure(
            "assistant_turn_convergence_timeout",
            "The active assistant turn did not finish in time.",
          ),
        }),
      options.convergenceTimeoutMs ?? DEFAULT_CONVERGENCE_TIMEOUT_MS,
    );
  });
}

function terminalEvent(
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

function requireTurnInProgress(
  state: RouteDeckClientState,
  requestId: string,
): void {
  const activeChat =
    state.projection?.interaction.phase === "active" &&
    state.projection.interaction.owner === "chat";
  const turnStarted =
    state.lastEvent?.event_type === "turn_started" &&
    state.lastEvent.payload.request_id === requestId;
  if (!activeChat && !turnStarted) {
    throw failure(
      "assistant_turn_convergence_unavailable",
      "No active assistant turn is available to restore.",
    );
  }
}

function isConflict(error: unknown): error is AgentChatError {
  return error instanceof AgentChatError && CONFLICT_CODES.has(error.code);
}

function requireRequestId(actual: string, expected: string): void {
  if (actual !== expected) {
    throw failure(
      "assistant_turn_request_identity_mismatch",
      "The assistant stream does not match the active request.",
    );
  }
}

function failure(code: string, message: string): AgentChatError {
  return new AgentChatError(code, message, null, "unknown");
}
