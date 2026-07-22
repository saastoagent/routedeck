import React from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter/index.css";
import "@fontsource/roboto-mono/latin-400.css";
import "@fontsource/roboto-mono/latin-500.css";
import { createRouteDeckAgentClient } from "@routedeck/core";

import { BootstrapLoadingShell } from "./app/BootstrapLoadingShell";
import { loadMedusaRouteDeck } from "./app/config";
import type { MedusaRouteDeck } from "./app/createRouteDeck";
import { MedusaApplicationRoot } from "./app/MedusaApplicationRoot";
import "./app/app.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Medusa Agent requires a #root element.");
}
const root = createRoot(rootElement);

renderLoading();

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
  root.render(
    <React.StrictMode>
      <MedusaApplicationRoot routeDeck={routeDeck} chatClient={chatClient} />
    </React.StrictMode>,
  );
}

function renderLoading(): void {
  root.render(<BootstrapLoadingShell />);
}

function errorMessage(error: unknown, unknownErrorMessage: string): string {
  return error instanceof Error ? error.message : unknownErrorMessage;
}
