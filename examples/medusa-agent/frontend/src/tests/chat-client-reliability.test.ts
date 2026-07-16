import { expect, it } from "vitest";

import {
  createRouteDeckAgentClient,
  type AgentAssistantTurnRequest,
  type AgentChatRequest,
  type AgentStreamEvent,
} from "@routedeck/core";


const REQUEST: AgentChatRequest = {
  request_id: "chat-http-stable",
  expected_session_version: 3,
  message: "Show my cart",
};

const ASSISTANT_REQUEST: AgentAssistantTurnRequest = {
  request_id: "assistant-http-stable",
  expected_session_version: 3,
};

it("loads the finalized public conversation through the RouteDeck endpoint", async () => {
  const requests: Array<{ input: string; init?: RequestInit }> = [];
  const client = createRouteDeckAgentClient({
    baseUrl: "https://agent.test/api/routedeck/",
    fetch: async (input, init) => {
      requests.push({ input: String(input), ...(init === undefined ? {} : { init }) });
      return Response.json({
        turns: [
          {
            turn_id: "turn-restored-1",
            request_id: "chat-restored-1",
            role: "assistant",
            content: "Your saved cart is ready.",
          },
        ],
      });
    },
  });

  await expect(client.loadConversation()).resolves.toEqual([
    {
      turn_id: "turn-restored-1",
      request_id: "chat-restored-1",
      role: "assistant",
      content: "Your saved cart is ready.",
    },
  ]);
  expect(requests).toEqual([
    {
      input: "https://agent.test/api/routedeck/conversation",
      init: {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      },
    },
  ]);
});

it("streams an assistant-initiated turn through the generic RouteDeck endpoint", async () => {
  const requests: Array<{ input: string; init?: RequestInit }> = [];
  const client = createRouteDeckAgentClient({
    baseUrl: "https://agent.test/api/routedeck/",
    fetch: async (input, init) => {
      requests.push({ input: String(input), ...(init === undefined ? {} : { init }) });
      return new Response(
        `${[
          "event: stream_start",
          'data: {"request_id":"assistant-http-stable","session_version":3}',
          "",
          "event: assistant_delta",
          'data: {"content":"Welcome.","request_id":"assistant-http-stable"}',
          "",
          "event: assistant_end",
          'data: {"request_id":"assistant-http-stable","session_version":4,"projection_version":4,"turn_id":"assistant-entry"}',
          "",
          "event: stream_end",
          'data: {"request_id":"assistant-http-stable","status":"completed"}',
          "",
        ].join("\n")}\n`,
        {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        },
      );
    },
  });

  await expect(collect(client.streamAssistantTurn(ASSISTANT_REQUEST))).resolves.toEqual([
    {
      type: "stream_start",
      request_id: "assistant-http-stable",
      session_version: 3,
    },
    {
      type: "assistant_delta",
      content: "Welcome.",
      request_id: "assistant-http-stable",
    },
    {
      type: "assistant_end",
      request_id: "assistant-http-stable",
      session_version: 4,
      projection_version: 4,
      turn_id: "assistant-entry",
    },
    {
      type: "stream_end",
      request_id: "assistant-http-stable",
      status: "completed",
    },
  ]);
  expect(requests).toEqual([
    {
      input: "https://agent.test/api/routedeck/conversation/assistant-turn",
      init: {
        method: "POST",
        credentials: "include",
        headers: {
          Accept: "text/event-stream",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(ASSISTANT_REQUEST),
      },
    },
  ]);
});


it("preserves a typed in-stream RouteDeck rejection", async () => {
  const client = createRouteDeckAgentClient({
    baseUrl: "https://agent.test/api/routedeck/",
    fetch: async () =>
      new Response(
        `${[
          "event: chat_error",
          'data: {"code":"operation_in_progress","message":"The RouteDeck session request could not be completed."}',
          "",
          "event: stream_end",
          'data: {"request_id":"assistant-http-stable","status":"rejected"}',
          "",
        ].join("\n")}\n`,
        {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        },
      ),
  });

  await expect(collect(client.streamAssistantTurn(ASSISTANT_REQUEST))).resolves.toEqual([
    {
      type: "chat_error",
      code: "operation_in_progress",
      message: "The RouteDeck session request could not be completed.",
    },
    {
      type: "stream_end",
      request_id: "assistant-http-stable",
      status: "rejected",
    },
  ]);
});


it("classifies a received chat 5xx as outcome unknown", async () => {
  const client = createRouteDeckAgentClient({
    baseUrl: "https://agent.test",
    fetch: async () =>
      Response.json(
        {
          failure: {
            code: "internal_failure",
            message: "The buyer-agent request failed.",
          },
        },
        { status: 500 },
      ),
  });

  await expect(collect(client.stream(REQUEST))).rejects.toMatchObject({
    status: 500,
    outcome: "unknown",
  });
});


it("keeps a received chat 4xx as a confirmed rejection", async () => {
  const client = createRouteDeckAgentClient({
    baseUrl: "https://agent.test",
    fetch: async () =>
      Response.json(
        {
          failure: {
            code: "version_conflict",
            message: "The session version is stale.",
          },
        },
        { status: 409 },
      ),
  });

  await expect(collect(client.stream(REQUEST))).rejects.toMatchObject({
    status: 409,
    outcome: "rejected",
  });
});


it("classifies a successful chat response without a body as outcome unknown", async () => {
  const client = createRouteDeckAgentClient({
    baseUrl: "https://agent.test",
    fetch: async () => new Response(null, { status: 200 }),
  });

  await expect(collect(client.stream(REQUEST))).rejects.toMatchObject({
    code: "stream_body_missing",
    status: 200,
    outcome: "unknown",
  });
});


async function collect(
  events: AsyncIterable<AgentStreamEvent>,
): Promise<AgentStreamEvent[]> {
  const collected: AgentStreamEvent[] = [];
  for await (const event of events) collected.push(event);
  return collected;
}
