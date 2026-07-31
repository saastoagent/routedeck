import "@testing-library/jest-dom/vitest";

import { StrictMode } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import {
  AgentChatError,
  createInitialRouteDeckState,
  type AgentHistoryTurn,
  type RouteDeckAgentClient,
  type RouteDeckClientState,
  type RouteDeckStore,
} from "@routedeck/core";
import { afterEach, expect, it, vi } from "vitest";

import type { MedusaRouteDeck } from "../app/createRouteDeck";
import { MedusaApplicationRoot } from "../app/MedusaApplicationRoot";

vi.mock("../app/App", () => ({
  App: ({ initialConversation }: { initialConversation: readonly AgentHistoryTurn[] }) => (
    <main>Buyer application with {initialConversation.length} turns</main>
  ),
}));

afterEach(cleanup);

it("bootstraps once under StrictMode and renders the restored conversation", async () => {
  const harness = createStoreHarness({ syncStatus: "idle" });
  harness.actions.bootstrap.mockImplementation(async () => {
    harness.setState({ syncStatus: "live" });
  });
  const chatClient = createChatClient();
  chatClient.loadConversation.mockResolvedValue([
    {
      turn_id: "assistant-1",
      request_id: "greeting-1",
      role: "assistant",
      content: "Welcome.",
    },
  ]);

  render(
    <StrictMode>
      <MedusaApplicationRoot
        routeDeck={asMedusaRouteDeck(harness.store)}
        chatClient={chatClient}
      />
    </StrictMode>,
  );

  expect(await screen.findByText("Buyer application with 1 turns")).toBeVisible();
  expect(harness.actions.bootstrap).toHaveBeenCalledOnce();
  expect(chatClient.loadConversation).toHaveBeenCalledOnce();
});

it("resyncs once and shows a conversation failure when history stays unavailable", async () => {
  const harness = createStoreHarness({ syncStatus: "live" });
  const chatClient = createChatClient();
  chatClient.loadConversation.mockRejectedValue(
    new AgentChatError(
      "session_not_found",
      "The buyer conversation session is missing.",
      404,
      "rejected",
    ),
  );

  render(
    <MedusaApplicationRoot
      routeDeck={asMedusaRouteDeck(harness.store)}
      chatClient={chatClient}
    />,
  );

  expect(
    await screen.findByRole("heading", {
      name: "Buyer conversation could not load",
    }),
  ).toBeVisible();
  await waitFor(() => expect(chatClient.loadConversation).toHaveBeenCalledTimes(2));
  expect(harness.actions.resync).toHaveBeenCalledOnce();
  expect(
    screen.queryByRole("heading", { name: "Medusa Agent needs session recovery" }),
  ).not.toBeInTheDocument();
});

it("returns to bootstrap recovery when the authoritative resync fails", async () => {
  const harness = createStoreHarness({ syncStatus: "live" });
  harness.actions.resync.mockImplementation(async () => {
    harness.setState({
      syncStatus: "error",
      error: {
        code: "session_unavailable",
        message: "The buyer session is unavailable.",
      },
    });
    throw new Error("transport failed");
  });
  const chatClient = createChatClient();
  chatClient.loadConversation.mockRejectedValue(
    new AgentChatError(
      "session_expired",
      "The buyer conversation session expired.",
      410,
      "rejected",
    ),
  );

  render(
    <MedusaApplicationRoot
      routeDeck={asMedusaRouteDeck(harness.store)}
      chatClient={chatClient}
    />,
  );

  expect(
    await screen.findByRole("heading", {
      name: "Medusa Agent needs session recovery",
    }),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Reconnect current buyer session" }),
  ).toBeVisible();
  expect(harness.actions.resync).toHaveBeenCalledOnce();
});

it("does not resync for an unrelated missing conversation endpoint", async () => {
  const harness = createStoreHarness({ syncStatus: "live" });
  const chatClient = createChatClient();
  chatClient.loadConversation.mockRejectedValue(
    new AgentChatError(
      "conversation_endpoint_missing",
      "The buyer conversation endpoint is unavailable.",
      404,
      "rejected",
    ),
  );

  render(
    <MedusaApplicationRoot
      routeDeck={asMedusaRouteDeck(harness.store)}
      chatClient={chatClient}
    />,
  );

  expect(
    await screen.findByRole("heading", {
      name: "Buyer conversation could not load",
    }),
  ).toBeVisible();
  expect(chatClient.loadConversation).toHaveBeenCalledOnce();
  expect(harness.actions.resync).not.toHaveBeenCalled();
});

function createChatClient() {
  return {
    loadConversation: vi.fn<RouteDeckAgentClient["loadConversation"]>(),
    startAssistantRun: vi.fn<RouteDeckAgentClient["startAssistantRun"]>(),
    loadConversationRun: vi.fn<RouteDeckAgentClient["loadConversationRun"]>(),
    async *streamConversationRunEvents() {},
    async *stream() {},
    async *streamAssistantTurn() {},
  } satisfies RouteDeckAgentClient;
}

function asMedusaRouteDeck(store: RouteDeckStore): MedusaRouteDeck {
  return { store } as MedusaRouteDeck;
}

function createStoreHarness(initial: Partial<RouteDeckClientState>) {
  let state: RouteDeckClientState = Object.freeze({
    ...createInitialRouteDeckState(),
    ...initial,
  });
  const listeners = new Set<() => void>();
  const setState = (next: Partial<RouteDeckClientState>) => {
    state = Object.freeze({ ...state, ...next });
    for (const listener of listeners) listener();
  };
  const actions = {
    bootstrap: vi.fn(async () => undefined),
    resync: vi.fn(async () => undefined),
    retrySessionCreate: vi.fn(async () => undefined),
    startNewSession: vi.fn(async () => undefined),
    retryNavigation: vi.fn(async () => undefined),
    abandonNavigation: vi.fn(async () => undefined),
  };
  const store: RouteDeckStore = {
    getState: () => state,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    bootstrap: actions.bootstrap,
    dispatch: async () => {
      throw new Error("Unexpected dispatch.");
    },
    acceptReview: async () => {
      throw new Error("Unexpected review acceptance.");
    },
    rejectReview: async () => {
      throw new Error("Unexpected review rejection.");
    },
    inspect: async () => {
      throw new Error("Unexpected inspection.");
    },
    receiveEvent() {},
    resync: actions.resync,
    synchronizeTo: async () => undefined,
    openPath: async () => undefined,
    back() {},
    forward() {},
    cancel: async () => undefined,
    retrySessionCreate: actions.retrySessionCreate,
    startNewSession: actions.startNewSession,
    retryNavigation: actions.retryNavigation,
    abandonNavigation: actions.abandonNavigation,
    dispose() {},
  };
  return { store, setState, actions };
}
