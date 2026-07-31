import { renderHook, waitFor } from "@testing-library/react";
import type {
  ConversationRunSnapshot,
  RouteDeckAgentClient,
} from "@routedeck/core";
import { useRouteDeckConversation } from "@routedeck/react";
import { expect, it, vi } from "vitest";

it("resubscribes an active run from the last accepted cursor", async () => {
  const eventCursors: number[] = [];
  let subscriptions = 0;
  const client = {
    async loadConversation() {
      return [];
    },
    async loadConversationRun() {
      return run("awaiting_model", 2, "");
    },
    async *streamConversationRunEvents(
      _requestId: string,
      after: number,
    ) {
      eventCursors.push(after);
      subscriptions += 1;
      if (subscriptions === 1) {
        yield run("generating", 3, "Hello");
        throw new TypeError("connection reset");
      }
      if (subscriptions <= 4) {
        throw new TypeError("connection still unavailable");
      }
      yield {
        ...run("completed", 4, "Hello again"),
        session_version: 3,
        projection_version: 3,
        turn_id: "assistant-final",
      };
    },
    async *stream() {},
    async *streamAssistantTurn() {},
    async startAssistantRun() {
      throw new Error("not used");
    },
  } satisfies RouteDeckAgentClient;
  const synchronizeTo = vi.fn(async () => undefined);

  const { result } = renderHook(() =>
    useRouteDeckConversation({
      client,
      sessionVersion: 1,
      createRequestId: () => "unused",
      synchronizeTo,
      resync: async () => undefined,
      activeRunRequestId: "active-run",
    }),
  );

  await waitFor(
    () => expect(result.current.status).not.toBe("streaming"),
    { timeout: 2_500 },
  );
  expect(
    {
      status: result.current.status,
      error: result.current.error === null
        ? undefined
        : `${result.current.error.code}: ${result.current.error.message}`,
      eventCursors,
    },
  ).toEqual({
    status: "idle",
    error: undefined,
    eventCursors: [2, 3, 3, 3, 3],
  });

  expect(synchronizeTo).toHaveBeenCalledWith({
    sessionVersion: 3,
    projectionVersion: 3,
  });
  expect(result.current.messages).toEqual([
    {
      id: "assistant-final",
      requestId: "active-run",
      role: "assistant",
      content: "Hello again",
      status: "finalized",
    },
  ]);
});

function run(
  stage: ConversationRunSnapshot["stage"],
  cursor: number,
  assistantContent: string,
): ConversationRunSnapshot {
  return {
    request_id: "active-run",
    kind: "assistant_initiated",
    stage,
    cursor,
    assistant_content: assistantContent,
    user_message: null,
    user_turn_id: null,
    session_version: null,
    projection_version: null,
    turn_id: null,
    failure: null,
    review: null,
  };
}
