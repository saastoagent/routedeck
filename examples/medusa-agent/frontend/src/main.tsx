import React from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter/index.css";
import "@fontsource/roboto-mono/latin-400.css";
import "@fontsource/roboto-mono/latin-500.css";
import {
  AgentChatError,
  createRouteDeckAgentClient,
} from "@routedeck/core";

import { App } from "./app/App";
import {
  BootstrapLoadingShell,
  type BootstrapLoadingPhase,
} from "./app/BootstrapLoadingShell";
import { BootstrapRecoveryShell } from "./app/BootstrapRecoveryShell";
import { loadMedusaRouteDeck } from "./app/config";
import type { MedusaRouteDeck } from "./app/createRouteDeck";
import {
  createGreetingRetryRequestId,
  loadInitialConversation,
} from "./app/initialConversation";
import "./app/app.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Medusa Agent requires a #root element.");
}
const root = createRoot(rootElement);

renderLoading("storefront");

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
  const renderApp = async (requestId?: string) => {
    const initialConversation = await loadInitialConversation(
      routeDeck,
      chatClient,
      {
        ...(requestId === undefined ? {} : { requestId }),
        onPhase: renderLoading,
      },
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
        <div className="bootstrap-actions">
          <button
            type="button"
            onClick={() => {
              renderLoading("checkout");
              void renderApp(createGreetingRetryRequestId()).catch(
                renderConversationError,
              );
            }}
          >
            Retry buyer conversation
          </button>
        </div>
      </section>,
    );
  };
  const restoreConversation = async () => {
    renderLoading("checkout");
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
    renderLoading("session");
    await routeDeck.store.bootstrap();
    await restoreConversation();
  } catch {
    renderRecovery();
  }
}

function renderLoading(phase: BootstrapLoadingPhase): void {
  root.render(<BootstrapLoadingShell phase={phase} />);
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
