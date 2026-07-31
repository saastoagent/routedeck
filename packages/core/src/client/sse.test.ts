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

it("rejects undeclared generated stream-reset fields", async () => {
  const connection = connectRouteDeckEvents({
    url: "https://routedeck.test/events",
    after: 8,
    reconnect: false,
    fetch: async () =>
      new Response(
        [
          "event: stream_reset_required",
          'data: {"event_type":"stream_reset_required","requested_after":8,"retained_from_cursor":9,"undeclared":true}',
          "",
          "",
        ].join("\n"),
        {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        },
      ),
    onEvent: () => undefined,
    onReset: () => undefined,
  });

  await expect(connection.done).rejects.toMatchObject({
    code: "stream_reset_invalid",
  });
});

it("applies generated defaults to a minimum stream-reset payload", async () => {
  const onReset = vi.fn();
  const connection = connectRouteDeckEvents({
    url: "https://routedeck.test/events",
    after: 8,
    reconnect: false,
    fetch: async () =>
      new Response(
        [
          "event: stream_reset_required",
          'data: {"requested_after":8}',
          "",
          "",
        ].join("\n"),
        {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        },
      ),
    onEvent: () => undefined,
    onReset,
  });

  await connection.done;

  expect(onReset).toHaveBeenCalledWith({
    event_type: "stream_reset_required",
    requested_after: 8,
    retained_from_cursor: null,
  });
});

it("validates an explicitly provided stream-reset event type", async () => {
  const connection = connectRouteDeckEvents({
    url: "https://routedeck.test/events",
    after: 8,
    reconnect: false,
    fetch: async () =>
      new Response(
        [
          "event: stream_reset_required",
          'data: {"event_type":"wrong","requested_after":8}',
          "",
          "",
        ].join("\n"),
        {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        },
      ),
    onEvent: () => undefined,
    onReset: () => undefined,
  });

  await expect(connection.done).rejects.toMatchObject({
    code: "stream_reset_invalid",
  });
});
