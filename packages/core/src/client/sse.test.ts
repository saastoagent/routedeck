import { expect, it, vi } from "vitest";

import { connectRouteDeckEvents } from "./sse";

it("reports a validated stream open before the stream can be considered live", async () => {
  const onOpen = vi.fn();
  const connection = connectRouteDeckEvents({
    url: "https://routedeck.test/events",
    after: 8,
    reconnect: false,
    fetch: async () =>
      new Response(": connected\n\n", {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
    onOpen,
    onEvent: () => undefined,
    onReset: () => undefined,
  });

  await connection.done;

  expect(onOpen).toHaveBeenCalledWith({
    after: 8,
    reconnecting: false,
  });
});

it.each([
  [404, "stream_session_not_found"],
  [410, "stream_session_expired"],
])(
  "stops reconnecting after terminal session HTTP %i",
  async (status, code) => {
    const fetch = vi.fn(async () =>
      new Response("{}", {
        status,
        headers: { "content-type": "application/json" },
      }),
    );
    const onError = vi.fn();
    const connection = connectRouteDeckEvents({
      url: "https://routedeck.test/events",
      after: 8,
      reconnect: true,
      reconnectDelayMs: 0,
      fetch,
      onError,
      onEvent: () => undefined,
      onReset: () => undefined,
    });

    await expect(connection.done).rejects.toMatchObject({
      code,
      retryable: false,
      status,
    });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledTimes(1);
  },
);
