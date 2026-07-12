import { expect, it } from "vitest";

import {
  createAgentChatClient,
  type AgentChatRequest,
  type AgentStreamEvent,
} from "../app/chatClient";


const REQUEST: AgentChatRequest = {
  request_id: "chat-http-stable",
  expected_session_version: 3,
  message: "Show my cart",
};

it("loads the finalized public conversation through the product read endpoint", async () => {
  const requests: Array<{ input: string; init?: RequestInit }> = [];
  const client = createAgentChatClient({
    baseUrl: "https://agent.test/api/medusa-agent/",
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
      input: "https://agent.test/api/medusa-agent/conversation",
      init: {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      },
    },
  ]);
});


it("classifies a received chat 5xx as outcome unknown", async () => {
  const client = createAgentChatClient({
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
  const client = createAgentChatClient({
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
  const client = createAgentChatClient({
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
