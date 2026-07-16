import {
  AgentChatError,
  type AgentHistoryTurn,
  type AgentStreamEvent,
  type RouteDeckAgentClient,
  type RouteDeckClientState,
  type RouteDeckStore,
} from "@routedeck/core";
import { afterEach, expect, it, vi } from "vitest";

import {
  INITIAL_GREETING_REQUEST_ID,
  createGreetingRetryRequestId,
  loadInitialConversation,
} from "../app/initialConversation";

const GREETING: AgentHistoryTurn = {
  turn_id: "turn-greeting",
  request_id: INITIAL_GREETING_REQUEST_ID,
  role: "assistant",
  content: "Welcome to Medusa.",
};

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("uses one stable session-scoped identity for the normal greeting", async () => {
  const harness = conversationHarness({
    conversationLoads: [[], [GREETING]],
    stream: completedGreetingStream(),
  });

  await expect(
    loadInitialConversation(harness.routeDeck, harness.chatClient),
  ).resolves.toEqual([GREETING]);

  expect(harness.assistantRequests).toEqual([
    {
      request_id: INITIAL_GREETING_REQUEST_ID,
      expected_session_version: 3,
    },
  ]);
  expect(harness.synchronizeTo).toHaveBeenCalledWith({
    sessionVersion: 4,
    projectionVersion: 4,
  });
});

it("waits for the winning greeting and reloads its durable conversation", async () => {
  const harness = conversationHarness({
    conversationLoads: [[], [], [GREETING]],
    stream: rejectedGreetingStream("operation_in_progress"),
    state: routeDeckState({
      sessionVersion: 4,
      projectionVersion: 3,
      interactionPhase: "active",
      lastEvent: routeDeckEvent("turn_started", 4, 3),
    }),
  });

  const loading = loadInitialConversation(
    harness.routeDeck,
    harness.chatClient,
  );
  await Promise.resolve();
  harness.publish(
    routeDeckState({
      sessionVersion: 5,
      projectionVersion: 4,
      interactionPhase: "idle",
      lastEvent: routeDeckEvent("turn_finalized", 5, 4),
    }),
  );

  await expect(loading).resolves.toEqual([GREETING]);
  expect(harness.assistantRequests).toHaveLength(1);
  expect(harness.synchronizeTo).toHaveBeenCalledWith({
    sessionVersion: 5,
    projectionVersion: 4,
  });
});

it("does not silently rerun a genuinely interrupted greeting", async () => {
  const harness = conversationHarness({
    conversationLoads: [[]],
    stream: rejectedGreetingStream("operation_in_progress"),
    state: routeDeckState({
      sessionVersion: 4,
      projectionVersion: 3,
      interactionPhase: "active",
      lastEvent: routeDeckEvent("turn_started", 4, 3),
    }),
  });

  const loading = loadInitialConversation(
    harness.routeDeck,
    harness.chatClient,
  );
  await Promise.resolve();
  harness.publish(
    routeDeckState({
      sessionVersion: 5,
      projectionVersion: 4,
      interactionPhase: "idle",
      lastEvent: routeDeckEvent("turn_interrupted", 5, 4),
    }),
  );

  await expect(loading).rejects.toMatchObject({
    code: "initial_greeting_interrupted",
  });
  expect(harness.assistantRequests).toHaveLength(1);
});

it("does not lose a terminal greeting event at subscription time", async () => {
  vi.useFakeTimers();
  const harness = conversationHarness({
    conversationLoads: [[], [], [GREETING]],
    stream: rejectedGreetingStream("operation_in_progress"),
    state: routeDeckState({
      sessionVersion: 4,
      projectionVersion: 3,
      interactionPhase: "active",
      lastEvent: routeDeckEvent("turn_started", 4, 3),
    }),
    beforeSubscribeState: routeDeckState({
      sessionVersion: 5,
      projectionVersion: 4,
      interactionPhase: "idle",
      lastEvent: routeDeckEvent("turn_finalized", 5, 4),
    }),
  });

  const loading = loadInitialConversation(
    harness.routeDeck,
    harness.chatClient,
  );
  await harness.subscriptionStarted;
  await vi.advanceTimersByTimeAsync(120_000);

  await expect(loading).resolves.toEqual([GREETING]);
});

it("creates a new identity only for an explicit greeting retry", () => {
  vi.stubGlobal("crypto", { randomUUID: () => "retry-uuid" });

  expect(createGreetingRetryRequestId()).toBe(
    "medusa.initial-greeting.v1.retry.retry-uuid",
  );
});

function conversationHarness(options: {
  conversationLoads: readonly (readonly AgentHistoryTurn[])[];
  stream: readonly AgentStreamEvent[];
  state?: RouteDeckClientState;
  beforeSubscribeState?: RouteDeckClientState;
}) {
  let state = options.state ?? routeDeckState({});
  const listeners = new Set<() => void>();
  let resolveSubscriptionStarted!: () => void;
  const subscriptionStarted = new Promise<void>((resolve) => {
    resolveSubscriptionStarted = resolve;
  });
  const loads = [...options.conversationLoads];
  const assistantRequests: Array<{
    request_id: string;
    expected_session_version: number;
  }> = [];
  const synchronizeTo = vi.fn(async () => undefined);
  const resync = vi.fn(async () => undefined);
  const store = {
    getState: () => state,
    subscribe: (listener: () => void) => {
      if (options.beforeSubscribeState !== undefined) {
        state = options.beforeSubscribeState;
      }
      listeners.add(listener);
      resolveSubscriptionStarted();
      return () => listeners.delete(listener);
    },
    resync,
    synchronizeTo,
  } as unknown as RouteDeckStore;
  const chatClient = {
    loadConversation: vi.fn(async () => loads.shift() ?? []),
    streamAssistantTurn: (request: {
      request_id: string;
      expected_session_version: number;
    }) => {
      assistantRequests.push(request);
      return scriptedStream(options.stream);
    },
  } as unknown as RouteDeckAgentClient;
  return {
    routeDeck: { store },
    chatClient,
    assistantRequests,
    synchronizeTo,
    subscriptionStarted,
    publish(next: RouteDeckClientState) {
      state = next;
      for (const listener of listeners) listener();
    },
  };
}

async function* scriptedStream(
  events: readonly AgentStreamEvent[],
): AsyncIterable<AgentStreamEvent> {
  for (const event of events) yield event;
}

function completedGreetingStream(): readonly AgentStreamEvent[] {
  return [
    {
      type: "stream_start",
      request_id: INITIAL_GREETING_REQUEST_ID,
      session_version: 3,
    },
    {
      type: "assistant_end",
      request_id: INITIAL_GREETING_REQUEST_ID,
      session_version: 4,
      projection_version: 4,
      turn_id: "turn-greeting",
    },
    {
      type: "stream_end",
      request_id: INITIAL_GREETING_REQUEST_ID,
      status: "completed",
    },
  ];
}

function rejectedGreetingStream(code: string): readonly AgentStreamEvent[] {
  return [
    {
      type: "chat_error",
      code,
      message: "The RouteDeck session request could not be completed.",
    },
    {
      type: "stream_end",
      request_id: INITIAL_GREETING_REQUEST_ID,
      status: "rejected",
    },
  ];
}

function routeDeckState(options: {
  sessionVersion?: number;
  projectionVersion?: number;
  interactionPhase?: "idle" | "active";
  lastEvent?: RouteDeckClientState["lastEvent"];
}): RouteDeckClientState {
  const interactionPhase = options.interactionPhase ?? "idle";
  return {
    projection: {
      interaction: {
        phase: interactionPhase,
        owner: interactionPhase === "active" ? "chat" : null,
      },
    } as RouteDeckClientState["projection"],
    sessionVersion: options.sessionVersion ?? 3,
    projectionVersion: options.projectionVersion ?? 3,
    eventCursor: options.lastEvent?.cursor ?? 0,
    syncStatus: "live",
    lastEvent: options.lastEvent ?? null,
    error: null,
    pendingBootstrap: null,
    pendingNavigation: null,
  };
}

function routeDeckEvent(
  eventType: "turn_started" | "turn_finalized" | "turn_interrupted",
  sessionVersion: number,
  projectionVersion: number,
): NonNullable<RouteDeckClientState["lastEvent"]> {
  return {
    created_at: "2026-07-16T12:00:00Z",
    cursor: sessionVersion,
    event_id: `event-${sessionVersion}`,
    event_type: eventType,
    payload: {
      node_id: "home",
      operation_id: null,
      request_id: INITIAL_GREETING_REQUEST_ID,
      status_code: eventType,
      entity_handles: [],
      details: [],
      failure: null,
    },
    projection_version: projectionVersion,
    session_version: sessionVersion,
  };
}
