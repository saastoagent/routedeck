import type { RouteDeckStore } from "../store/types";
import {
  AgentChatError,
  type AgentHistoryTurn,
  type ConversationRunSnapshot,
  type RouteDeckAgentClient,
} from "./types";

export interface AssistantInitiatedTurnOptions {
  requestId: string;
  onProgress?(progress: AssistantInitiatedTurnProgress): void;
}

export interface AssistantInitiatedTurnProgress {
  readonly requestId: string;
  readonly content: string;
}

type AssistantTurnStore = Pick<RouteDeckStore, "getState" | "synchronizeTo">;

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

  let run = await client.startAssistantRun({
    request_id: options.requestId,
    expected_session_version: sessionVersion,
  });
  requireRequestId(run.request_id, options.requestId);
  publishProgress(options, run);

  if (!terminal(run)) {
    const startingCursor = run.cursor;
    for await (const event of client.streamConversationRunEvents(
      options.requestId,
      startingCursor,
    )) {
      requireRequestId(event.request_id, options.requestId);
      if (event.cursor <= run.cursor) {
        throw failure(
          "assistant_run_cursor_regressed",
          "The assistant run event cursor did not advance.",
        );
      }
      run = event;
      publishProgress(options, run);
    }
  }

  if (!terminal(run)) {
    run = await client.loadConversationRun(options.requestId);
    requireRequestId(run.request_id, options.requestId);
    publishProgress(options, run);
  }
  if (run.stage === "interrupted") {
    throw new AgentChatError(
      run.failure?.code ?? "assistant_turn_interrupted",
      run.failure?.message ??
        "The assistant turn was interrupted. Retry it explicitly to continue.",
      null,
      "interrupted",
    );
  }
  if (
    run.stage !== "completed" ||
    run.session_version === null ||
    run.projection_version === null
  ) {
    throw failure(
      "assistant_run_incomplete",
      "The assistant run ended without a durable terminal result.",
    );
  }
  await store.synchronizeTo({
    sessionVersion: run.session_version,
    projectionVersion: run.projection_version,
  });
  return client.loadConversation();
}

function publishProgress(
  options: AssistantInitiatedTurnOptions,
  run: ConversationRunSnapshot,
): void {
  if (run.stage !== "generating" || options.onProgress === undefined) return;
  options.onProgress(
    Object.freeze({
      requestId: options.requestId,
      content: run.assistant_content,
    }),
  );
}

function terminal(run: ConversationRunSnapshot): boolean {
  return run.stage === "completed" || run.stage === "interrupted";
}

function requireRequestId(actual: string, expected: string): void {
  if (actual !== expected) {
    throw failure(
      "assistant_turn_request_identity_mismatch",
      "The assistant run does not match the active request.",
    );
  }
}

function failure(code: string, message: string): AgentChatError {
  return new AgentChatError(code, message, null, "unknown");
}
