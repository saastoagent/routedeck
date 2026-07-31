import { describe, expect, it, vi } from "vitest";

import {
  createRouteDeckAgentClient,
  isRouteDeckConversationSessionRecoveryError,
} from "./client";
import { AgentChatError } from "./types";

describe("RouteDeck conversation failures", () => {
  it("starts a reconnectable assistant run and decodes accumulated progress", async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/conversation/runs")) {
        return runResponse("starting", 1);
      }
      return new Response(
        [
          ": connected\n\n",
          `id: 2\nevent: conversation_run\ndata: ${JSON.stringify(runValue("generating", 2, { assistant_content: "Wel" }))}\n\n`,
          `id: 3\nevent: conversation_run\ndata: ${JSON.stringify(runValue("completed", 3, {
            assistant_content: "Welcome.",
            session_version: 4,
            projection_version: 4,
            turn_id: "turn-assistant",
          }))}\n\n`,
        ].join(""),
        { headers: { "Content-Type": "text/event-stream" } },
      );
    });
    const client = createRouteDeckAgentClient({ fetch: fetcher });

    const started = await client.startAssistantRun({
      request_id: "entry-1",
      expected_session_version: 3,
    });
    const events = [];
    for await (const event of client.streamConversationRunEvents("entry-1", 1)) {
      events.push(event);
    }

    expect(started.stage).toBe("starting");
    expect(events.map((event) => [event.cursor, event.stage, event.assistant_content]))
      .toEqual([
        [2, "generating", "Wel"],
        [3, "completed", "Welcome."],
      ]);
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "/api/routedeck/conversation/runs/entry-1/events?after=1",
      expect.objectContaining({ method: "GET", cache: "no-store" }),
    );
  });

  it("decodes the canonical RouteDeck failure envelope", async () => {
    const fetcher = vi.fn(async () => canonicalFailureResponse(
      404,
      "session_not_found",
      "The RouteDeck session request could not be completed.",
    ));
    const client = createRouteDeckAgentClient({ fetch: fetcher });

    const failure = await client.loadConversation().catch((error: unknown) => error);

    expect(failure).toMatchObject({
      code: "session_not_found",
      message: "The RouteDeck session request could not be completed.",
      status: 404,
      outcome: "rejected",
    });
    expect(isRouteDeckConversationSessionRecoveryError(failure)).toBe(true);
  });

  it("decodes a privacy-safe recovered interrupted user run", async () => {
    const fetcher = vi.fn(async () => new Response(
      JSON.stringify({
        run: runValue("interrupted", 9_007_199_254_740_991, {
          kind: "user_message",
          user_message: null,
          user_turn_id: null,
          failure: { code: "turn_interrupted", message: "Interrupted." },
        }),
      }),
      { headers: { "Content-Type": "application/json" } },
    ));
    const client = createRouteDeckAgentClient({ fetch: fetcher });

    await expect(client.loadConversationRun("entry-1")).resolves.toMatchObject({
      kind: "user_message",
      stage: "interrupted",
      user_message: null,
      user_turn_id: null,
    });
  });

  it("does not classify an unrelated HTTP error as session recovery", () => {
    const failure = new AgentChatError(
      "conversation_endpoint_missing",
      "The conversation endpoint is unavailable.",
      404,
      "rejected",
    );

    expect(isRouteDeckConversationSessionRecoveryError(failure)).toBe(false);
  });

  it("fails explicitly when the server returns the retired compact envelope", async () => {
    const fetcher = vi.fn(async () => new Response(
      JSON.stringify({
        failure: {
          code: "session_not_found",
          message: "The session is missing.",
        },
      }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    ));
    const client = createRouteDeckAgentClient({ fetch: fetcher });

    await expect(client.loadConversation()).rejects.toMatchObject({
      code: "chat_contract_invalid",
      status: 404,
    });
  });

  it("rejects undeclared generated conversation history fields", async () => {
    const fetcher = vi.fn(async () => new Response(
      JSON.stringify({ turns: [], undeclared: true }),
      { headers: { "Content-Type": "application/json" } },
    ));
    const client = createRouteDeckAgentClient({ fetch: fetcher });

    await expect(client.loadConversation()).rejects.toMatchObject({
      code: "chat_contract_invalid",
    });
  });

  it("rejects undeclared generated conversation turn fields", async () => {
    const fetcher = vi.fn(async () => new Response(
      JSON.stringify({
        turns: [{
          turn_id: "turn-1",
          request_id: null,
          role: "assistant",
          content: "Hello",
          undeclared: true,
        }],
      }),
      { headers: { "Content-Type": "application/json" } },
    ));
    const client = createRouteDeckAgentClient({ fetch: fetcher });

    await expect(client.loadConversation()).rejects.toMatchObject({
      code: "chat_contract_invalid",
    });
  });

  it("rejects undeclared generated conversation run fields", async () => {
    const fetcher = vi.fn(async () => new Response(
      JSON.stringify({
        run: { ...runValue("starting", 1), undeclared: true },
      }),
      { headers: { "Content-Type": "application/json" } },
    ));
    const client = createRouteDeckAgentClient({ fetch: fetcher });

    await expect(client.loadConversationRun("entry-1")).rejects.toMatchObject({
      code: "conversation_run_contract_invalid",
    });
  });
});

function runValue(
  stage: "starting" | "generating" | "completed" | "interrupted",
  cursor: number,
  overrides: Record<string, unknown> = {},
) {
  return {
    request_id: "entry-1",
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

function runResponse(
  stage: "starting" | "generating" | "completed",
  cursor: number,
): Response {
  return new Response(JSON.stringify({ run: runValue(stage, cursor) }), {
    status: stage === "completed" ? 200 : 202,
    headers: { "Content-Type": "application/json" },
  });
}

function canonicalFailureResponse(
  status: number,
  code: string,
  publicMessage: string,
): Response {
  return new Response(
    JSON.stringify({
      failure: {
        kind: "persistence",
        code,
        phase: "session_store",
        correlation_id: "conversation-failure-1",
        operation_id: null,
        request_id: null,
        public_message: publicMessage,
        recovery_directive: null,
        safe_details: {
          affected_capability: null,
          provider: null,
          provider_code: null,
          http_status: null,
          delivery_phase: null,
        },
      },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}
