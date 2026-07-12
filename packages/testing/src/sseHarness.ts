import type { RouteDeckEvent, RouteDeckFetch } from "@routedeck/core";

export function routeDeckSseFrame(event: RouteDeckEvent): string {
  return [
    `id: ${event.cursor}`,
    `event: ${event.event_type}`,
    `data: ${JSON.stringify(event)}`,
    "",
    "",
  ].join("\n");
}

export function createSseFetchHarness(frames: readonly string[]): {
  fetch: RouteDeckFetch;
  requests: Array<{ url: string; lastEventId: string | null }>;
} {
  const requests: Array<{ url: string; lastEventId: string | null }> = [];
  const encoder = new TextEncoder();
  return {
    requests,
    async fetch(input, init) {
      const headers = new Headers(init?.headers);
      requests.push({
        url: String(input),
        lastEventId: headers.get("last-event-id"),
      });
      return new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            for (const frame of frames) controller.enqueue(encoder.encode(frame));
            controller.close();
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        },
      );
    },
  };
}
