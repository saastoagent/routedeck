import { describe, expect, it, vi } from "vitest";

import type { RouteDeckClientState } from "../store/state";
import type { RouteDeckStore } from "../store/types";
import { runAssistantInitiatedTurn } from "./assistant";
import type {
  AgentHistoryTurn,
  ConversationRunSnapshot,
  RouteDeckAgentClient,
} from "./types";

const REQUEST_ID = "application.entry.v1";
const ASSISTANT_TURN: AgentHistoryTurn = {
  turn_id: "turn-assistant",
  request_id: REQUEST_ID,
  role: "assistant",
  content: "Welcome.",
};

describe("runAssistantInitiatedTurn", () => {
  it("publishes accumulated progress and synchronizes durable completion", async () => {
    const harness = assistantHarness({
      started: run("starting", 1),
      events: [
        run("awaiting_model", 2),
        run("generating", 3, { assistant_content: "Wel" }),
        run("generating", 4, { assistant_content: "Welcome." }),
        run("completed", 5, {
          assistant_content: "Welcome.",
          session_version: 4,
          projection_version: 4,
          turn_id: "turn-assistant",
        }),
      ],
    });
    const progress: string[] = [];

    await expect(
      runAssistantInitiatedTurn(harness.store, harness.client, {
        requestId: REQUEST_ID,
        onProgress: (update) => progress.push(update.content),
      }),
    ).resolves.toEqual([ASSISTANT_TURN]);

    expect(progress).toEqual(["Wel", "Welcome."]);
    expect(harness.startAssistantRun).toHaveBeenCalledWith({
      request_id: REQUEST_ID,
      expected_session_version: 3,
    });
    expect(harness.streamConversationRunEvents).toHaveBeenCalledWith(
      REQUEST_ID,
      1,
    );
    expect(harness.synchronizeTo).toHaveBeenCalledWith({
      sessionVersion: 4,
      projectionVersion: 4,
    });
  });

  it("attaches to an already completed run without subscribing", async () => {
    const harness = assistantHarness({
      started: run("completed", 1, {
        assistant_content: "Welcome.",
        session_version: 4,
        projection_version: 4,
        turn_id: "turn-assistant",
      }),
      events: [],
    });

    await expect(
      runAssistantInitiatedTurn(harness.store, harness.client, {
        requestId: REQUEST_ID,
      }),
    ).resolves.toEqual([ASSISTANT_TURN]);

    expect(harness.streamConversationRunEvents).not.toHaveBeenCalled();
  });

  it("reports a durable interrupted run without rerunning it", async () => {
    const harness = assistantHarness({
      started: run("starting", 1),
      events: [
        run("interrupted", 2, {
          failure: { code: "turn_interrupted", message: "Interrupted." },
        }),
      ],
    });

    await expect(
      runAssistantInitiatedTurn(harness.store, harness.client, {
        requestId: REQUEST_ID,
      }),
    ).rejects.toMatchObject({
      code: "turn_interrupted",
      outcome: "interrupted",
    });
    expect(harness.startAssistantRun).toHaveBeenCalledOnce();
  });

  it("rejects a non-monotonic event cursor", async () => {
    const harness = assistantHarness({
      started: run("starting", 2),
      events: [run("generating", 2, { assistant_content: "Welcome" })],
    });

    await expect(
      runAssistantInitiatedTurn(harness.store, harness.client, {
        requestId: REQUEST_ID,
      }),
    ).rejects.toMatchObject({ code: "assistant_run_cursor_regressed" });
  });

  it("requires an available synchronized session", async () => {
    const harness = assistantHarness({
      started: run("starting", 1),
      events: [],
      sessionVersion: null,
    });

    await expect(
      runAssistantInitiatedTurn(harness.store, harness.client, {
        requestId: REQUEST_ID,
      }),
    ).rejects.toMatchObject({ code: "routedeck_session_unavailable" });
    expect(harness.startAssistantRun).not.toHaveBeenCalled();
  });
});

function assistantHarness(options: {
  started: ConversationRunSnapshot;
  events: readonly ConversationRunSnapshot[];
  sessionVersion?: number | null;
}) {
  const synchronizeTo = vi.fn(async () => undefined);
  const store = {
    getState: () => ({
      sessionVersion:
        options.sessionVersion === undefined ? 3 : options.sessionVersion,
    } as RouteDeckClientState),
    synchronizeTo,
  } as unknown as RouteDeckStore;
  const startAssistantRun = vi.fn(async () => options.started);
  const streamConversationRunEvents = vi.fn(
    (_requestId: string, _after: number) => scriptedEvents(options.events),
  );
  const client = {
    startAssistantRun,
    streamConversationRunEvents,
    loadConversationRun: vi.fn(async () => options.started),
    loadConversation: vi.fn(async () => [ASSISTANT_TURN]),
  } as unknown as RouteDeckAgentClient;
  return {
    store,
    client,
    startAssistantRun,
    streamConversationRunEvents,
    synchronizeTo,
  };
}

async function* scriptedEvents(
  events: readonly ConversationRunSnapshot[],
): AsyncIterable<ConversationRunSnapshot> {
  for (const event of events) yield event;
}

function run(
  stage: ConversationRunSnapshot["stage"],
  cursor: number,
  overrides: Partial<ConversationRunSnapshot> = {},
): ConversationRunSnapshot {
  return {
    request_id: REQUEST_ID,
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
    ...overrides,
  };
}
