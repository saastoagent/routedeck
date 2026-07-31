import { describe, expect, it } from "vitest";

import {
  parseAgentSse,
  validateAgentAssistantTurnRequest,
  validateAgentChatRequest,
} from "./codec";

const LEGACY_PAYLOADS = [
  [
    "stream_start",
    { request_id: "request-1", session_version: 0 },
  ],
  [
    "conversation_snapshot",
    {
      turns: [
        {
          turn_id: "turn-1",
          request_id: null,
          role: "assistant",
          content: "",
        },
      ],
    },
  ],
  [
    "user_message",
    { content: "Hello", request_id: "request-1", turn_id: "turn-1" },
  ],
  [
    "assistant_delta",
    { content: "Hello", request_id: "request-1" },
  ],
  ["assistant_reset", { request_id: "request-1" }],
  [
    "assistant_end",
    {
      request_id: "request-1",
      session_version: 2,
      projection_version: 3,
      turn_id: "turn-1",
    },
  ],
  [
    "review_required",
    {
      status: "requires_review",
      operation_id: "operation-1",
      review_id: "review-1",
      expires_at: "2026-07-31T12:00:00+00:00",
    },
  ],
  [
    "chat_error",
    { code: "turn_interrupted", message: "Interrupted." },
  ],
  [
    "stream_end",
    { request_id: "request-1", status: "completed" },
  ],
] as const;

describe("legacy public conversation SSE contracts", () => {
  it("accepts every Python-declared maximum field set", async () => {
    const events = await decodeFrames(
      LEGACY_PAYLOADS.map(([event, payload]) => frame(event, payload)).join(""),
    );

    expect(events.map((event) => event.type)).toEqual(
      LEGACY_PAYLOADS.map(([event]) => event),
    );
  });

  it("accepts minimum and maximum legal transport numbers", async () => {
    const events = await decodeFrames(
      [
        frame("stream_start", {
          request_id: "x".repeat(256),
          session_version: 0,
        }),
        frame("assistant_end", {
          request_id: "x".repeat(256),
          session_version: Number.MAX_SAFE_INTEGER,
          projection_version: Number.MAX_SAFE_INTEGER,
          turn_id: "turn-max",
        }),
      ].join(""),
    );

    expect(events).toMatchObject([
      { type: "stream_start", session_version: 0 },
      {
        type: "assistant_end",
        session_version: Number.MAX_SAFE_INTEGER,
        projection_version: Number.MAX_SAFE_INTEGER,
      },
    ]);
  });

  it.each([
    ["stream_start", { request_id: "x".repeat(257), session_version: 0 }],
    [
      "user_message",
      { content: "Hello", request_id: "x".repeat(257), turn_id: "turn-1" },
    ],
    [
      "assistant_delta",
      { content: "Hello", request_id: "x".repeat(257) },
    ],
    ["assistant_reset", { request_id: "x".repeat(257) }],
    [
      "assistant_end",
      {
        request_id: "x".repeat(257),
        session_version: 0,
        projection_version: 0,
        turn_id: "turn-1",
      },
    ],
    ["stream_end", { request_id: "x".repeat(257), status: "completed" }],
  ])("rejects an overlong %s request ID", async (event, payload) => {
    await expect(decodeFrames(frame(event, payload))).rejects.toMatchObject({
      code: "chat_contract_invalid",
    });
  });

  it.each([
    [
      "stream_start",
      { request_id: "request-1", session_version: 9_007_199_254_740_992 },
    ],
    [
      "assistant_end",
      {
        request_id: "request-1",
        session_version: 9_007_199_254_740_992,
        projection_version: 0,
        turn_id: "turn-1",
      },
    ],
    [
      "assistant_end",
      {
        request_id: "request-1",
        session_version: 0,
        projection_version: 9_007_199_254_740_992,
        turn_id: "turn-1",
      },
    ],
  ])("rejects an unsafe %s version", async (event, payload) => {
    await expect(decodeFrames(frame(event, payload))).rejects.toMatchObject({
      code: "chat_contract_invalid",
    });
  });

  it("matches canonical empty-string legality for public history turns", async () => {
    await expect(
      decodeFrames(frame("conversation_snapshot", {
        turns: [{
          turn_id: "turn-1",
          request_id: "",
          role: "assistant",
          content: "",
        }],
      })),
    ).resolves.toMatchObject([{
      type: "conversation_snapshot",
      turns: [{ turn_id: "turn-1", request_id: "" }],
    }]);

    await expect(
      decodeFrames(frame("conversation_snapshot", {
        turns: [{
          turn_id: "",
          request_id: null,
          role: "assistant",
          content: "",
        }],
      })),
    ).rejects.toMatchObject({ code: "chat_contract_invalid" });
  });

  it("rejects overlong outbound legacy request IDs", () => {
    expect(() => validateAgentChatRequest({
      request_id: "x".repeat(257),
      expected_session_version: 0,
      message: "Hello",
    })).toThrowError(expect.objectContaining({ code: "chat_contract_invalid" }));
    expect(() => validateAgentAssistantTurnRequest({
      request_id: "x".repeat(257),
      expected_session_version: 0,
    })).toThrowError(expect.objectContaining({ code: "chat_contract_invalid" }));
  });

  it("counts Unicode code points for inbound legacy request IDs", async () => {
    const boundary = "\u{1F680}".repeat(256);
    const overlong = "\u{1F680}".repeat(257);

    await expect(
      decodeFrames(frame("stream_start", {
        request_id: boundary,
        session_version: 0,
      })),
    ).resolves.toMatchObject([{
      type: "stream_start",
      request_id: boundary,
    }]);
    await expect(
      decodeFrames(frame("stream_start", {
        request_id: overlong,
        session_version: 0,
      })),
    ).rejects.toMatchObject({ code: "chat_contract_invalid" });
  });

  it("counts Unicode code points for outbound legacy request IDs", () => {
    const boundary = "\u{1F680}".repeat(256);
    const overlong = "\u{1F680}".repeat(257);

    expect(() => validateAgentChatRequest({
      request_id: boundary,
      expected_session_version: 0,
      message: "Hello",
    })).not.toThrow();
    expect(() => validateAgentAssistantTurnRequest({
      request_id: boundary,
      expected_session_version: 0,
    })).not.toThrow();
    expect(() => validateAgentChatRequest({
      request_id: overlong,
      expected_session_version: 0,
      message: "Hello",
    })).toThrowError(expect.objectContaining({ code: "chat_contract_invalid" }));
    expect(() => validateAgentAssistantTurnRequest({
      request_id: overlong,
      expected_session_version: 0,
    })).toThrowError(expect.objectContaining({ code: "chat_contract_invalid" }));
  });

  it.each(LEGACY_PAYLOADS)(
    "rejects an undeclared %s payload field",
    async (event, payload) => {
      await expect(
        decodeFrames(frame(event, { ...payload, undeclared: true })),
      ).rejects.toMatchObject({ code: "chat_contract_invalid" });
    },
  );

  it.each(LEGACY_PAYLOADS)(
    "rejects a missing required %s payload field",
    async (event, payload) => {
      const [required] = Object.keys(payload);
      const incomplete = { ...payload } as Record<string, unknown>;
      delete incomplete[required!];

      await expect(
        decodeFrames(frame(event, incomplete)),
      ).rejects.toMatchObject({ code: "chat_contract_invalid" });
    },
  );
});

async function decodeFrames(source: string) {
  const body = new Response(source).body;
  if (body === null) throw new Error("test response body missing");
  const events = [];
  for await (const event of parseAgentSse(body)) events.push(event);
  return events;
}

function frame(event: string, payload: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`;
}
