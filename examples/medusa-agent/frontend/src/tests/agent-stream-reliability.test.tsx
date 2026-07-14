import { act, renderHook, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import {
  AgentChatError,
  type AgentChatClient,
  type AgentChatRequest,
  type AgentStreamEvent,
} from "@routedeck/core";
import { useRouteDeckConversation } from "@routedeck/react";

it("starts from bootstrap history without posting a new chat turn", () => {
  const streamCalls: AgentChatRequest[] = [];
  const client: AgentChatClient = {
    async *stream(request) {
      streamCalls.push(request);
    },
  };
  const { result } = renderHook(() =>
    useRouteDeckConversation({
      client,
      initialConversation: [
        {
          turn_id: "restored-assistant-turn",
          request_id: "restored-chat",
          role: "assistant",
          content: "Your durable conversation is restored.",
        },
      ],
      sessionVersion: 3,
      createRequestId: () => "unused-request-id",
      synchronizeTo: async () => undefined,
      resync: async () => undefined,
    }),
  );

  expect(result.current.messages).toEqual([
    {
      id: "restored-assistant-turn",
      requestId: "restored-chat",
      role: "assistant",
      content: "Your durable conversation is restored.",
      status: "finalized",
    },
  ]);
  expect(streamCalls).toEqual([]);
});

it("does not let a late conversation snapshot clobber an in-flight response", async () => {
  const client: AgentChatClient = {
    async *stream(request) {
      yield {
        type: "user_message",
        request_id: request.request_id,
        turn_id: "live-user-turn",
        content: request.message,
      } as const;
      yield {
        type: "assistant_delta",
        request_id: request.request_id,
        content: "Live answer",
      } as const;
      yield {
        type: "conversation_snapshot",
        turns: [
          {
            turn_id: "older-assistant-turn",
            request_id: "older-chat",
            role: "assistant",
            content: "Older answer",
          },
        ],
      } as const;
      yield {
        type: "assistant_end",
        request_id: request.request_id,
        session_version: 4,
        projection_version: 4,
        turn_id: "live-assistant-turn",
      } as const;
      yield {
        type: "stream_end",
        request_id: request.request_id,
        status: "completed",
      } as const;
    },
  };
  const { result } = renderHook(() =>
    useRouteDeckConversation({
      client,
      sessionVersion: 3,
      createRequestId: () => "live-chat",
      synchronizeTo: async () => undefined,
      resync: async () => undefined,
    }),
  );

  await act(async () => result.current.send("Keep this live turn"));

  expect(result.current.messages).toEqual([
    expect.objectContaining({ id: "older-assistant-turn" }),
    expect.objectContaining({ id: "live-user-turn", content: "Keep this live turn" }),
    expect.objectContaining({
      id: "live-assistant-turn",
      content: "Live answer",
      status: "finalized",
    }),
  ]);
});

it("replaces a partial assistant with the canonical completed replay turn", async () => {
  let attempt = 0;
  const client: AgentChatClient = {
    async *stream(request) {
      attempt += 1;
      if (attempt === 1) {
        yield {
          type: "user_message",
          request_id: request.request_id,
          turn_id: "canonical-user-turn",
          content: request.message,
        } as const;
        yield {
          type: "assistant_delta",
          request_id: request.request_id,
          content: "Partial answer",
        } as const;
        throw new TypeError("connection closed after partial assistant output");
      }
      yield {
        type: "stream_start",
        request_id: request.request_id,
        session_version: 2,
      } as const;
      yield {
        type: "conversation_snapshot",
        turns: [
          {
            turn_id: "canonical-user-turn",
            request_id: request.request_id,
            role: "user",
            content: request.message,
          },
          {
            turn_id: "canonical-assistant-turn",
            request_id: request.request_id,
            role: "assistant",
            content: "Canonical completed answer",
          },
        ],
      } as const;
      yield {
        type: "assistant_end",
        request_id: request.request_id,
        session_version: 2,
        projection_version: 2,
        turn_id: "canonical-assistant-turn",
      } as const;
      yield {
        type: "stream_end",
        request_id: request.request_id,
        status: "completed",
      } as const;
    },
  };
  const { result } = renderHook(() =>
    useRouteDeckConversation({
      client,
      sessionVersion: 1,
      createRequestId: () => "replayed-chat",
      synchronizeTo: async () => undefined,
      resync: async () => undefined,
    }),
  );

  await act(async () => {
    await expect(result.current.send("Restore the completed answer")).rejects.toMatchObject({
      code: "chat_stream_failed",
      outcome: "unknown",
    });
  });
  expect(result.current.messages).toEqual([
    expect.objectContaining({ id: "canonical-user-turn", role: "user" }),
    expect.objectContaining({
      id: "assistant:replayed-chat",
      role: "assistant",
      content: "Partial answer",
      status: "streaming",
    }),
  ]);

  await act(async () => result.current.retry());

  expect(result.current.messages).toEqual([
    {
      id: "canonical-user-turn",
      requestId: "replayed-chat",
      role: "user",
      content: "Restore the completed answer",
      status: "finalized",
    },
    {
      id: "canonical-assistant-turn",
      requestId: "replayed-chat",
      role: "assistant",
      content: "Canonical completed answer",
      status: "finalized",
    },
  ]);
});

it("retains an outcome-unknown chat request and retries the exact request id", async () => {
  const requests: AgentChatRequest[] = [];
  let attempt = 0;
  const client: AgentChatClient = {
    async *stream(request) {
      requests.push(structuredClone(request));
      attempt += 1;
      if (attempt === 1) throw new TypeError("response connection closed");
      yield* completedTurn(request.request_id, 2, 2);
    },
  };
  const createRequestId = vi.fn(() => "chat-request-stable");
  const synchronizeTo = vi.fn(async () => undefined);
  const { result } = renderHook(() =>
    useRouteDeckConversation({
      client,
      sessionVersion: 1,
      createRequestId,
      synchronizeTo,
      resync: async () => undefined,
    }),
  );

  await act(async () => {
    await expect(result.current.send("Show me products")).rejects.toMatchObject({
      code: "chat_stream_failed",
    });
  });

  expect(result.current.pendingRequest).toMatchObject({
    requestId: "chat-request-stable",
    message: "Show me products",
  });
  expect(createRequestId).toHaveBeenCalledOnce();

  await act(async () => {
    await result.current.retry();
  });

  expect(requests.map((request) => request.request_id)).toEqual([
    "chat-request-stable",
    "chat-request-stable",
  ]);
  expect(requests[1]).toEqual(requests[0]);
  expect(result.current.pendingRequest).toBeNull();
  expect(result.current.status).toBe("idle");
});

it("keeps the composer-busy stream state until RouteDeck reaches assistant_end", async () => {
  let releaseSynchronization!: () => void;
  const synchronization = new Promise<void>((resolve) => {
    releaseSynchronization = resolve;
  });
  const synchronizeTo = vi.fn(() => synchronization);
  const client: AgentChatClient = {
    async *stream(request) {
      yield* completedTurn(request.request_id, 4, 3);
    },
  };
  const { result } = renderHook(() =>
    useRouteDeckConversation({
      client,
      sessionVersion: 2,
      createRequestId: () => "chat-version-sync",
      synchronizeTo,
      resync: async () => undefined,
    }),
  );

  let sending!: Promise<void>;
  act(() => {
    sending = result.current.send("Open my cart");
  });
  await waitFor(() =>
    expect(synchronizeTo).toHaveBeenCalledWith({
      sessionVersion: 4,
      projectionVersion: 3,
    }),
  );
  expect(result.current.status).toBe("streaming");

  await act(async () => {
    releaseSynchronization();
    await sending;
  });
  expect(result.current.status).toBe("idle");
});

it("removes an interrupted turn that authoritative history did not commit", async () => {
  const client: AgentChatClient = {
    async *stream(request) {
      yield {
        type: "conversation_snapshot",
        turns: [
          {
            turn_id: "prior-turn",
            request_id: null,
            role: "assistant",
            content: "Earlier answer",
          },
        ],
      };
      yield {
        type: "user_message",
        request_id: request.request_id,
        turn_id: "uncommitted-user-turn",
        content: request.message,
      };
      yield {
        type: "stream_end",
        request_id: request.request_id,
        status: "turn_interrupted",
      };
    },
  };
  const { result } = renderHook(() =>
    useRouteDeckConversation({
      client,
      sessionVersion: 2,
      createRequestId: () => "chat-interrupted",
      synchronizeTo: async () => undefined,
      resync: async () => undefined,
    }),
  );

  await act(async () => {
    await expect(result.current.send("Place the order")).rejects.toEqual(
      expect.objectContaining<Partial<AgentChatError>>({
        code: "chat_turn_interrupted",
      }),
    );
  });

  expect(result.current.messages).toEqual([
    expect.objectContaining({ id: "prior-turn", content: "Earlier answer" }),
  ]);
  expect(result.current.pendingRequest).toBeNull();
});

it("retains the exact request when interruption persistence leaves the outcome unknown", async () => {
  const client: AgentChatClient = {
    async *stream(request) {
      yield {
        type: "conversation_snapshot",
        turns: [
          {
            turn_id: "prior-turn",
            request_id: null,
            role: "assistant",
            content: "Earlier answer",
          },
        ],
      };
      yield {
        type: "user_message",
        request_id: request.request_id,
        turn_id: "unresolved-user-turn",
        content: request.message,
      };
      yield {
        type: "stream_end",
        request_id: request.request_id,
        status: "outcome_unknown",
      };
    },
  };
  const { result } = renderHook(() =>
    useRouteDeckConversation({
      client,
      sessionVersion: 2,
      createRequestId: () => "chat-outcome-unknown",
      synchronizeTo: async () => undefined,
      resync: async () => undefined,
    }),
  );

  await act(async () => {
    await expect(result.current.send("Place the order")).rejects.toEqual(
      expect.objectContaining<Partial<AgentChatError>>({
        code: "chat_turn_outcome_unknown",
        outcome: "unknown",
      }),
    );
  });

  expect(result.current.messages).toEqual([
    expect.objectContaining({ id: "prior-turn", content: "Earlier answer" }),
  ]);
  expect(result.current.pendingRequest).toMatchObject({
    requestId: "chat-outcome-unknown",
    message: "Place the order",
  });
});

it("retains the exact chat request when the buyer stops an in-flight response", async () => {
  const requests: AgentChatRequest[] = [];
  let attempt = 0;
  const client: AgentChatClient = {
    async *stream(request, signal) {
      requests.push(structuredClone(request));
      attempt += 1;
      if (attempt === 1) {
        await new Promise<void>((_resolve, reject) => {
          signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Stopped", "AbortError")),
            { once: true },
          );
        });
        return;
      }
      yield* completedTurn(request.request_id, 3, 2);
    },
  };
  const { result } = renderHook(() =>
    useRouteDeckConversation({
      client,
      sessionVersion: 1,
      createRequestId: () => "chat-stop-stable",
      synchronizeTo: async () => undefined,
      resync: async () => undefined,
    }),
  );

  let sending!: Promise<void>;
  act(() => {
    sending = result.current.send("Show my cart");
  });
  await waitFor(() => expect(result.current.status).toBe("streaming"));
  act(() => result.current.cancel());
  await act(async () => {
    await expect(sending).rejects.toMatchObject({
      code: "chat_turn_outcome_unknown",
      outcome: "unknown",
    });
  });

  expect(result.current.pendingRequest).toMatchObject({
    requestId: "chat-stop-stable",
    message: "Show my cart",
  });
  expect(result.current.status).toBe("error");

  await act(async () => result.current.retry());
  expect(requests).toHaveLength(2);
  expect(requests[1]).toEqual(requests[0]);
  expect(result.current.pendingRequest).toBeNull();
});

async function* completedTurn(
  requestId: string,
  sessionVersion: number,
  projectionVersion: number,
): AsyncGenerator<AgentStreamEvent> {
  yield {
    type: "stream_start",
    request_id: requestId,
    session_version: sessionVersion - 1,
  };
  yield {
    type: "user_message",
    request_id: requestId,
    turn_id: `user:${requestId}`,
    content: "Buyer request",
  };
  yield {
    type: "assistant_delta",
    request_id: requestId,
    content: "Done",
  };
  yield {
    type: "assistant_end",
    request_id: requestId,
    session_version: sessionVersion,
    projection_version: projectionVersion,
    turn_id: `assistant:${requestId}:final`,
  };
  yield {
    type: "stream_end",
    request_id: requestId,
    status: "completed",
  };
}
