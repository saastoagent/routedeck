import React from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter/index.css";
import "@fontsource/roboto-mono/latin-400.css";
import "@fontsource/roboto-mono/latin-500.css";
import {
  AgentChatError,
  createRouteDeckAgentClient,
  type AgentHistoryTurn,
  type RouteDeckAgentClient,
} from "@routedeck/core";

import { App } from "./app/App";
import { BootstrapRecoveryShell } from "./app/BootstrapRecoveryShell";
import { loadMedusaRouteDeck } from "./app/config";
import type { MedusaRouteDeck } from "./app/createRouteDeck";
import "./app/app.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Medusa Agent requires a #root element.");
}
const root = createRoot(rootElement);

void start();

async function start(): Promise<void> {
  let routeDeck: MedusaRouteDeck;
  try {
    routeDeck = await loadMedusaRouteDeck(window);
  } catch (error) {
    root.render(
      <section className="bootstrap-error" role="alert">
        <h1>Medusa Agent could not load</h1>
        <p>
          {errorMessage(
            error,
            "The RouteDeck contract could not be loaded.",
          )}
        </p>
      </section>,
    );
    return;
  }

  window.addEventListener("pagehide", () => routeDeck.store.dispose(), {
    once: true,
  });
  const chatClient = createRouteDeckAgentClient();
  const renderApp = async () => {
    const initialConversation = await loadInitialConversation(
      routeDeck,
      chatClient,
    );
    root.render(
      <React.StrictMode>
        <App
          routeDeck={routeDeck}
          chatClient={chatClient}
          initialConversation={initialConversation}
        />
      </React.StrictMode>,
    );
  };
  const renderRecovery = () => {
    root.render(
      <React.StrictMode>
        <BootstrapRecoveryShell
          store={routeDeck.store}
          onReady={() => void restoreConversation()}
        />
      </React.StrictMode>,
    );
  };
  const renderConversationError = (error: unknown) => {
    root.render(
      <section className="bootstrap-error" role="alert">
        <h1>Buyer conversation could not load</h1>
        <p>
          {errorMessage(
            error,
            "The saved buyer conversation could not be restored.",
          )}
        </p>
      </section>,
    );
  };
  const restoreConversation = async () => {
    try {
      await renderApp();
    } catch (error) {
      if (!isMissingOrExpiredSession(error)) {
        renderConversationError(error);
        return;
      }
      try {
        await routeDeck.store.resync();
        await renderApp();
      } catch {
        renderRecovery();
      }
    }
  };

  try {
    await routeDeck.store.bootstrap();
    await restoreConversation();
  } catch {
    renderRecovery();
  }
}

async function loadInitialConversation(
  routeDeck: MedusaRouteDeck,
  chatClient: RouteDeckAgentClient,
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
  const requestId = entryRequestId();
  let completedVersions:
    | { sessionVersion: number; projectionVersion: number }
    | null = null;
  let streamCompleted = false;
  try {
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
          throw new AgentChatError(
            event.code,
            event.message,
            null,
            "rejected",
          );
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
  } catch (error) {
    if (error instanceof AgentChatError && error.status === 409) {
      return chatClient.loadConversation();
    }
    throw error;
  }
  if (!streamCompleted || completedVersions === null) {
    throw assistantTurnFailure(
      "assistant_turn_stream_incomplete",
      "The buyer greeting ended without a durable assistant completion.",
    );
  }
  await routeDeck.store.synchronizeTo({
    sessionVersion: completedVersions.sessionVersion,
    projectionVersion: completedVersions.projectionVersion,
  });
  return chatClient.loadConversation();
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

function entryRequestId(): string {
  const identifier = globalThis.crypto.randomUUID();
  if (!identifier) {
    throw new AgentChatError(
      "entry_request_id_unavailable",
      "The browser could not create a buyer greeting request ID.",
    );
  }
  return `entry_${identifier}`;
}

function isMissingOrExpiredSession(error: unknown): boolean {
  return (
    error instanceof AgentChatError &&
    (error.status === 404 || error.status === 410)
  );
}

function errorMessage(error: unknown, unknownErrorMessage: string): string {
  return error instanceof Error ? error.message : unknownErrorMessage;
}
