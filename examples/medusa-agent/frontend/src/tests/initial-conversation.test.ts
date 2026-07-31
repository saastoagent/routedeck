import {
  AgentChatError,
  type AgentHistoryTurn,
  type ConversationRunSnapshot,
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
  vi.unstubAllGlobals();
});

it("uses one stable session-scoped identity for the normal greeting", async () => {
  const harness = conversationHarness({
    conversationLoads: [[], [GREETING]],
    initialRun: completedGreetingRun(),
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

it("attaches to the active greeting and reloads its durable conversation", async () => {
  const harness = conversationHarness({
    conversationLoads: [[], [GREETING]],
    initialRun: activeGreetingRun(),
    events: [completedGreetingRun(3)],
  });

  await expect(
    loadInitialConversation(harness.routeDeck, harness.chatClient),
  ).resolves.toEqual([GREETING]);
  expect(harness.assistantRequests).toHaveLength(1);
  expect(harness.synchronizeTo).toHaveBeenCalledWith({
    sessionVersion: 4,
    projectionVersion: 4,
  });
});

it("does not silently rerun a genuinely interrupted greeting", async () => {
  const harness = conversationHarness({
    conversationLoads: [[]],
    initialRun: activeGreetingRun(),
    events: [interruptedGreetingRun()],
  });

  await expect(
    loadInitialConversation(harness.routeDeck, harness.chatClient),
  ).rejects.toMatchObject({
    code: "initial_greeting_interrupted",
  });
  expect(harness.assistantRequests).toHaveLength(1);
});

it("loads the terminal greeting when an event subscription ends", async () => {
  const harness = conversationHarness({
    conversationLoads: [[], [GREETING]],
    initialRun: activeGreetingRun(),
    loadedRun: completedGreetingRun(3),
  });

  await expect(
    loadInitialConversation(harness.routeDeck, harness.chatClient),
  ).resolves.toEqual([GREETING]);
});

it("creates a new identity only for an explicit greeting retry", () => {
  vi.stubGlobal("crypto", { randomUUID: () => "retry-uuid" });

  expect(createGreetingRetryRequestId()).toBe(
    "medusa.initial-greeting.v1.retry.retry-uuid",
  );
});

function conversationHarness(options: {
  conversationLoads: readonly (readonly AgentHistoryTurn[])[];
  initialRun: ConversationRunSnapshot;
  events?: readonly ConversationRunSnapshot[];
  loadedRun?: ConversationRunSnapshot;
  state?: RouteDeckClientState;
}) {
  let state = options.state ?? routeDeckState({});
  const loads = [...options.conversationLoads];
  const assistantRequests: Array<{
    request_id: string;
    expected_session_version: number;
  }> = [];
  const synchronizeTo = vi.fn(async () => undefined);
  const resync = vi.fn(async () => undefined);
  const store = {
    getState: () => state,
    subscribe: () => () => undefined,
    resync,
    synchronizeTo,
  } as unknown as RouteDeckStore;
  const chatClient = {
    loadConversation: vi.fn(async () => loads.shift() ?? []),
    startAssistantRun: vi.fn(async (request: {
      request_id: string;
      expected_session_version: number;
    }) => {
      assistantRequests.push(request);
      return options.initialRun;
    }),
    loadConversationRun: vi.fn(async () => options.loadedRun ?? options.initialRun),
    streamConversationRunEvents: () => scriptedRunStream(options.events ?? []),
  } as unknown as RouteDeckAgentClient;
  return {
    routeDeck: { store },
    chatClient,
    assistantRequests,
    synchronizeTo,
  };
}

async function* scriptedRunStream(
  events: readonly ConversationRunSnapshot[],
): AsyncIterable<ConversationRunSnapshot> {
  for (const event of events) yield event;
}

function activeGreetingRun(cursor = 1): ConversationRunSnapshot {
  return greetingRun("awaiting_model", cursor);
}

function completedGreetingRun(cursor = 2): ConversationRunSnapshot {
  return {
    ...greetingRun("completed", cursor),
    assistant_content: GREETING.content,
    session_version: 4,
    projection_version: 4,
    turn_id: GREETING.turn_id,
  };
}

function interruptedGreetingRun(): ConversationRunSnapshot {
  return {
    ...greetingRun("interrupted", 2),
    failure: {
      code: "assistant_turn_interrupted",
      message: "The assistant turn was interrupted. Retry it explicitly to continue.",
    },
  };
}

function greetingRun(
  stage: ConversationRunSnapshot["stage"],
  cursor: number,
): ConversationRunSnapshot {
  return {
    request_id: INITIAL_GREETING_REQUEST_ID,
    kind: "assistant_initiated",
    stage,
    cursor,
    assistant_content: "",
    user_message: null,
    user_turn_id: null,
    session_version: null,
    projection_version: null,
    turn_id: null,
    failure: null,
    review: null,
  };
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
