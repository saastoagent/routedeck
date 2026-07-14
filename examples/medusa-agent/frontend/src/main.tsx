import React from "react";
import { createRoot } from "react-dom/client";
import {
  AgentChatError,
  createRouteDeckAgentClient,
} from "@routedeck/core";

import { App } from "./app/App";
import { BootstrapRecoveryShell } from "./app/BootstrapRecoveryShell";
import { startMedusaConversation } from "./app/conversationEntryClient";
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
  chatClient: ReturnType<typeof createRouteDeckAgentClient>,
) {
  const existing = await chatClient.loadConversation();
  if (existing.length > 0) return existing;
  const sessionVersion = routeDeck.store.getState().sessionVersion;
  if (sessionVersion === null) {
    throw new AgentChatError(
      "routedeck_session_unavailable",
      "The RouteDeck session is unavailable for the buyer greeting.",
    );
  }
  const entry = await startMedusaConversation({
    request_id: entryRequestId(),
    expected_session_version: sessionVersion,
  });
  await routeDeck.store.synchronizeTo({
    sessionVersion: entry.sessionVersion,
    projectionVersion: entry.projectionVersion,
  });
  return chatClient.loadConversation();
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
