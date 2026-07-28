import { afterEach, describe, expect, it, vi } from "vitest";

import type { RouteDeckClientState } from "../store/state";
import type { RouteDeckStore } from "../store/types";
import {
  AgentChatError,
  type AgentHistoryTurn,
  type AgentStreamEvent,
  type RouteDeckAgentClient,
} from "./types";
import { runAssistantInitiatedTurn } from "./assistant";

const REQUEST_ID = "application.entry.v1";
const ASSISTANT_TURN: AgentHistoryTurn = {
  turn_id: "turn-assistant",
  request_id: REQUEST_ID,
  role: "assistant",
  content: "Welcome.",
};

afterEach(() => {
  vi.useRealTimers();
});

describe("runAssistantInitiatedTurn", () => {
  it("publishes accumulated assistant progress before returning durable conversation", async () => {
    let releaseCompletion!: () => void;
    const completionGate = new Promise<void>((resolve) => {
      releaseCompletion = resolve;
    });
    const harness = assistantHarness({
      conversationLoads: [[ASSISTANT_TURN]],
      stream: gatedAssistantStream(completionGate),
    });
    const progress: string[] = [];

    let completed = false;
    const loading = runAssistantInitiatedTurn(harness.store, harness.client, {
      requestId: REQUEST_ID,
      onProgress: (update) => progress.push(update.content),
    }).then((conversation) => {
      completed = true;
      return conversation;
    });

    await vi.waitFor(() => expect(progress).toEqual(["Wel"]));
    expect(completed).toBe(false);
    releaseCompletion();
    await loading;

    expect(progress).toEqual(["Wel", "Welcome."]);
  });

  it("commits one completed assistant turn and reloads durable conversation", async () => {
    const harness = assistantHarness({
      conversationLoads: [[ASSISTANT_TURN]],
      stream: completedAssistantStream(),
    });

    await expect(
      runAssistantInitiatedTurn(harness.store, harness.client, {
        requestId: REQUEST_ID,
      }),
    ).resolves.toEqual([ASSISTANT_TURN]);

    expect(harness.assistantRequests).toEqual([
      { request_id: REQUEST_ID, expected_session_version: 3 },
    ]);
    expect(harness.synchronizeTo).toHaveBeenCalledWith({
      sessionVersion: 4,
      projectionVersion: 4,
    });
  });

  it.each([
    {
      name: "duplicate assistant completion",
      events: [
        ...completedAssistantStream().slice(0, 2),
        completedAssistantStream()[1]!,
        completedAssistantStream()[2]!,
      ],
      code: "assistant_turn_completion_duplicate",
    },
    {
      name: "unexpected user message",
      events: [
        completedAssistantStream()[0]!,
        {
          type: "user_message" as const,
          content: "unexpected",
          request_id: REQUEST_ID,
          turn_id: "turn-user",
        },
      ],
      code: "assistant_turn_user_message_forbidden",
    },
    {
      name: "unexpected review",
      events: [
        completedAssistantStream()[0]!,
        {
          type: "review_required" as const,
          status: "requires_review" as const,
          operation_id: "operation",
          review_id: "review",
          expires_at: "2026-07-20T12:00:00Z",
        },
      ],
      code: "assistant_turn_review_forbidden",
    },
    {
      name: "incomplete stream",
      events: completedAssistantStream().slice(0, 2),
      code: "assistant_turn_stream_incomplete",
    },
  ])("rejects $name", async ({ events, code }) => {
    const harness = assistantHarness({
      conversationLoads: [],
      stream: events,
    });

    await expect(
      runAssistantInitiatedTurn(harness.store, harness.client, {
        requestId: REQUEST_ID,
      }),
    ).rejects.toMatchObject({ code });
  });

  it("waits for a conflicting winning turn and returns its durable conversation", async () => {
    const harness = assistantHarness({
      conversationLoads: [[], [ASSISTANT_TURN]],
      stream: rejectedAssistantStream("operation_in_progress"),
      state: routeDeckState({
        sessionVersion: 4,
        projectionVersion: 3,
        interactionPhase: "active",
        lastEvent: routeDeckEvent("turn_started", 4, 3),
      }),
    });

    const loading = runAssistantInitiatedTurn(harness.store, harness.client, {
      requestId: REQUEST_ID,
    });
    await Promise.resolve();
    harness.publish(
      routeDeckState({
        sessionVersion: 5,
        projectionVersion: 4,
        interactionPhase: "idle",
        lastEvent: routeDeckEvent("turn_finalized", 5, 4),
      }),
    );

    await expect(loading).resolves.toEqual([ASSISTANT_TURN]);
    expect(harness.assistantRequests).toHaveLength(1);
    expect(harness.resync).toHaveBeenCalledOnce();
    expect(harness.synchronizeTo).toHaveBeenCalledWith({
      sessionVersion: 5,
      projectionVersion: 4,
    });
  });

  it("reports a genuinely interrupted conflicting turn without rerunning it", async () => {
    const harness = assistantHarness({
      conversationLoads: [[]],
      stream: rejectedAssistantStream("version_conflict"),
      state: routeDeckState({
        sessionVersion: 4,
        projectionVersion: 3,
        interactionPhase: "active",
        lastEvent: routeDeckEvent("turn_started", 4, 3),
      }),
    });

    const loading = runAssistantInitiatedTurn(harness.store, harness.client, {
      requestId: REQUEST_ID,
    });
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
      code: "assistant_turn_interrupted",
      outcome: "interrupted",
    });
    expect(harness.assistantRequests).toHaveLength(1);
  });

  it("does not lose a terminal event published at subscription time", async () => {
    vi.useFakeTimers();
    const harness = assistantHarness({
      conversationLoads: [[], [ASSISTANT_TURN]],
      stream: rejectedAssistantStream("operation_in_progress"),
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

    const loading = runAssistantInitiatedTurn(harness.store, harness.client, {
      requestId: REQUEST_ID,
      convergenceTimeoutMs: 50,
    });
    await harness.subscriptionStarted;
    await vi.advanceTimersByTimeAsync(50);

    await expect(loading).resolves.toEqual([ASSISTANT_TURN]);
  });

  it("requires an available synchronized session", async () => {
    const harness = assistantHarness({
      conversationLoads: [],
      stream: [],
      state: routeDeckState({ sessionVersion: null }),
    });

    await expect(
      runAssistantInitiatedTurn(harness.store, harness.client, {
        requestId: REQUEST_ID,
      }),
    ).rejects.toMatchObject({ code: "routedeck_session_unavailable" });
    expect(harness.assistantRequests).toEqual([]);
  });
});

function assistantHarness(options: {
  conversationLoads: readonly (readonly AgentHistoryTurn[])[];
  stream: readonly AgentStreamEvent[] | AsyncIterable<AgentStreamEvent>;
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
  const client = {
    loadConversation: vi.fn(async () => loads.shift() ?? []),
    streamAssistantTurn: (request: {
      request_id: string;
      expected_session_version: number;
    }) => {
      assistantRequests.push(request);
      return Symbol.asyncIterator in options.stream
        ? options.stream
        : scriptedStream(options.stream);
    },
  } as unknown as RouteDeckAgentClient;
  return {
    store,
    client,
    assistantRequests,
    synchronizeTo,
    resync,
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

async function* gatedAssistantStream(
  completionGate: Promise<void>,
): AsyncIterable<AgentStreamEvent> {
  yield {
    type: "stream_start",
    request_id: REQUEST_ID,
    session_version: 3,
  };
  yield {
    type: "assistant_delta",
    request_id: REQUEST_ID,
    content: "Wel",
  };
  await completionGate;
  yield {
    type: "assistant_delta",
    request_id: REQUEST_ID,
    content: "come.",
  };
  yield {
    type: "assistant_end",
    request_id: REQUEST_ID,
    session_version: 4,
    projection_version: 4,
    turn_id: "turn-assistant",
  };
  yield {
    type: "stream_end",
    request_id: REQUEST_ID,
    status: "completed",
  };
}

function completedAssistantStream(): readonly AgentStreamEvent[] {
  return [
    {
      type: "stream_start",
      request_id: REQUEST_ID,
      session_version: 3,
    },
    {
      type: "assistant_end",
      request_id: REQUEST_ID,
      session_version: 4,
      projection_version: 4,
      turn_id: "turn-assistant",
    },
    {
      type: "stream_end",
      request_id: REQUEST_ID,
      status: "completed",
    },
  ];
}

function rejectedAssistantStream(code: string): readonly AgentStreamEvent[] {
  return [
    {
      type: "chat_error",
      code,
      message: "The RouteDeck session request could not be completed.",
    },
    {
      type: "stream_end",
      request_id: REQUEST_ID,
      status: "rejected",
    },
  ];
}

function routeDeckState(options: {
  sessionVersion?: number | null;
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
    sessionVersion:
      options.sessionVersion === undefined ? 3 : options.sessionVersion,
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
    created_at: "2026-07-20T12:00:00Z",
    cursor: sessionVersion,
    event_id: `event-${sessionVersion}`,
    event_type: eventType,
    payload: {
      node_id: "home",
      operation_id: null,
      request_id: REQUEST_ID,
      status_code: eventType,
      entity_handles: [],
      details: [],
      failure: null,
    },
    projection_version: projectionVersion,
    session_version: sessionVersion,
  };
}
