import React from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import { BootstrapRecoveryShell } from "./app/BootstrapRecoveryShell";
import {
  AgentChatError,
  createAgentChatClient,
} from "./app/chatClient";
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
  const chatClient = createAgentChatClient();
  const renderApp = async () => {
    const initialConversation = await chatClient.loadConversation();
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

function isMissingOrExpiredSession(error: unknown): boolean {
  return (
    error instanceof AgentChatError &&
    (error.status === 404 || error.status === 410)
  );
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
