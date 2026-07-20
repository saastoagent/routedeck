import {
  AgentChatError,
  runAssistantInitiatedTurn,
  type AgentHistoryTurn,
  type RouteDeckAgentClient,
  type RouteDeckStore,
} from "@routedeck/core";

export const INITIAL_GREETING_REQUEST_ID = "medusa.initial-greeting.v1";

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

  try {
    return await runAssistantInitiatedTurn(routeDeck.store, chatClient, {
      requestId: options.requestId ?? INITIAL_GREETING_REQUEST_ID,
    });
  } catch (error) {
    throw greetingError(error);
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

const GREETING_ERRORS: Readonly<Record<string, { code: string; message: string }>> =
  Object.freeze({
    routedeck_session_unavailable: {
      code: "routedeck_session_unavailable",
      message: "The RouteDeck session is unavailable for the buyer greeting.",
    },
    assistant_turn_projection_unavailable: {
      code: "initial_greeting_projection_unavailable",
      message: "The completed buyer greeting did not publish a projection version.",
    },
    assistant_turn_interrupted: {
      code: "initial_greeting_interrupted",
      message: "The buyer greeting was interrupted. Retry it explicitly to continue.",
    },
    assistant_turn_not_committed: {
      code: "initial_greeting_not_committed",
      message: "The buyer greeting completed without a durable conversation turn.",
    },
    assistant_turn_convergence_failed: {
      code: "initial_greeting_convergence_failed",
      message: "RouteDeck could not observe the active buyer greeting.",
    },
    assistant_turn_convergence_lost: {
      code: "initial_greeting_convergence_lost",
      message: "The active buyer greeting ended without its terminal event.",
    },
    assistant_turn_convergence_timeout: {
      code: "initial_greeting_convergence_timeout",
      message: "The active buyer greeting did not finish in time.",
    },
    assistant_turn_convergence_unavailable: {
      code: "initial_greeting_convergence_unavailable",
      message: "No active buyer greeting is available to restore.",
    },
  });

function greetingError(error: unknown): unknown {
  if (!(error instanceof AgentChatError)) return error;
  const replacement = GREETING_ERRORS[error.code];
  if (replacement === undefined) return error;
  return new AgentChatError(
    replacement.code,
    error.code === "assistant_turn_interrupted" &&
      error.message !==
        "The assistant turn was interrupted. Retry it explicitly to continue."
      ? error.message
      : replacement.message,
    error.status,
    error.outcome,
  );
}
