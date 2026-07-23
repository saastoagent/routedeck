import { useCallback, useEffect, useRef, useState } from "react";
import {
  isRouteDeckConversationSessionRecoveryError,
  type AgentHistoryTurn,
  type RouteDeckAgentClient,
} from "@routedeck/core";
import { RouteDeckBootstrapBoundary } from "@routedeck/react";

import { App } from "./App";
import { BootstrapLoadingShell } from "./BootstrapLoadingShell";
import { BootstrapRecoveryShell } from "./BootstrapRecoveryShell";
import type { MedusaRouteDeck } from "./createRouteDeck";
import {
  createGreetingRetryRequestId,
  loadInitialConversation,
} from "./initialConversation";

export interface MedusaApplicationRootProps {
  routeDeck: MedusaRouteDeck;
  chatClient: RouteDeckAgentClient;
}

export function MedusaApplicationRoot({
  routeDeck,
  chatClient,
}: MedusaApplicationRootProps) {
  return (
    <RouteDeckBootstrapBoundary
      store={routeDeck.store}
      loading={<BootstrapLoadingShell />}
      recovery={(state) => <BootstrapRecoveryShell state={state} />}
    >
      <InitialConversationGate routeDeck={routeDeck} chatClient={chatClient} />
    </RouteDeckBootstrapBoundary>
  );
}

function InitialConversationGate({
  routeDeck,
  chatClient,
}: MedusaApplicationRootProps) {
  const [attempt, setAttempt] = useState<ConversationAttempt>({ sequence: 0 });
  const [result, setResult] = useState<ConversationLoadState>({
    phase: "loading",
  });
  const retained = useRef<RetainedConversationLoad | null>(null);

  useEffect(() => {
    let active = true;
    let load = retained.current;
    if (load === null || load.sequence !== attempt.sequence) {
      load = {
        sequence: attempt.sequence,
        promise: restoreInitialConversation(
          routeDeck,
          chatClient,
          attempt.requestId,
        ),
      };
      retained.current = load;
    }
    void load.promise.then(
      (conversation) => {
        if (active) setResult({ phase: "ready", conversation });
      },
      (error: unknown) => {
        if (active) setResult({ phase: "error", error });
      },
    );
    return () => {
      active = false;
    };
  }, [attempt, chatClient, routeDeck]);

  const retry = useCallback(() => {
    setResult({ phase: "loading" });
    setAttempt((current) => ({
      sequence: current.sequence + 1,
      requestId: createGreetingRetryRequestId(),
    }));
  }, []);

  if (result.phase === "loading") return <BootstrapLoadingShell />;
  if (result.phase === "error") {
    return (
      <section className="bootstrap-error" role="alert">
        <h1>Buyer conversation could not load</h1>
        <p>
          {errorMessage(
            result.error,
            "The saved buyer conversation could not be restored.",
          )}
        </p>
        <div className="bootstrap-actions">
          <button type="button" onClick={retry}>
            Retry buyer conversation
          </button>
        </div>
      </section>
    );
  }
  return (
    <App
      routeDeck={routeDeck}
      chatClient={chatClient}
      initialConversation={result.conversation}
    />
  );
}

async function restoreInitialConversation(
  routeDeck: MedusaRouteDeck,
  chatClient: RouteDeckAgentClient,
  requestId?: string,
): Promise<readonly AgentHistoryTurn[]> {
  try {
    return await loadConversation(routeDeck, chatClient, requestId);
  } catch (error) {
    if (!isRouteDeckConversationSessionRecoveryError(error)) throw error;
    await routeDeck.store.resync();
    return loadConversation(routeDeck, chatClient, requestId);
  }
}

function loadConversation(
  routeDeck: MedusaRouteDeck,
  chatClient: RouteDeckAgentClient,
  requestId?: string,
): Promise<readonly AgentHistoryTurn[]> {
  return loadInitialConversation(
    routeDeck,
    chatClient,
    requestId === undefined ? {} : { requestId },
  );
}

function errorMessage(error: unknown, unknownErrorMessage: string): string {
  return error instanceof Error ? error.message : unknownErrorMessage;
}

interface ConversationAttempt {
  readonly sequence: number;
  readonly requestId?: string;
}

interface RetainedConversationLoad {
  readonly sequence: number;
  readonly promise: Promise<readonly AgentHistoryTurn[]>;
}

type ConversationLoadState =
  | Readonly<{ phase: "loading" }>
  | Readonly<{
      phase: "ready";
      conversation: readonly AgentHistoryTurn[];
    }>
  | Readonly<{ phase: "error"; error: unknown }>;
