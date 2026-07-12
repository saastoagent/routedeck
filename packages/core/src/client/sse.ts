import { decodeEvent, type RouteDeckEvent } from "../contracts/decode";
import type { RouteDeckFetch } from "./http";
import {
  RouteDeckContractError,
  RouteDeckStreamError,
} from "./errors";

export interface RouteDeckStreamReset {
  event_type: "stream_reset_required";
  requested_after: number;
  retained_from_cursor: number | null;
}

export interface RouteDeckStreamOpen {
  after: number;
  reconnecting: boolean;
}

export interface RouteDeckEventConnection {
  close(): void;
  readonly done: Promise<void>;
}

export interface RouteDeckEventStreamOptions {
  url: string;
  after: number;
  fetch?: RouteDeckFetch;
  credentials?: RequestCredentials;
  reconnect?: boolean;
  reconnectDelayMs?: number;
  onEvent(event: RouteDeckEvent): void;
  onReset(reset: RouteDeckStreamReset): void;
  onOpen?(open: RouteDeckStreamOpen): void;
  onError?(error: RouteDeckStreamError): void;
}

interface ParsedSseFrame {
  id: string | null;
  event: string | null;
  data: string;
}

export function connectRouteDeckEvents(
  options: RouteDeckEventStreamOptions,
): RouteDeckEventConnection {
  if (!Number.isInteger(options.after) || options.after < 0) {
    throw new RouteDeckContractError("$sse.after", "expected a non-negative integer");
  }
  const fetchImplementation = options.fetch ?? globalThis.fetch?.bind(globalThis);
  if (!fetchImplementation) {
    throw new RouteDeckStreamError(
      "stream_fetch_unavailable",
      "A fetch implementation is required for RouteDeck SSE.",
    );
  }
  const controller = new AbortController();
  let cursor = options.after;
  let attempt = 0;
  const done = follow();

  async function follow(): Promise<void> {
    while (!controller.signal.aborted) {
      attempt += 1;
      try {
        const reset = await consumeOnce(attempt > 1);
        if (reset || controller.signal.aborted || options.reconnect === false) return;
        await waitForReconnect(
          options.reconnectDelayMs ?? 1_000,
          controller.signal,
        );
      } catch (error) {
        if (controller.signal.aborted) return;
        const streamError =
          error instanceof RouteDeckStreamError
            ? error
            : new RouteDeckStreamError(
                "stream_failed",
                "The RouteDeck event stream failed.",
                { cause: error },
              );
        options.onError?.(streamError);
        if (!streamError.retryable || options.reconnect === false) {
          throw streamError;
        }
        await waitForReconnect(
          options.reconnectDelayMs ?? 1_000,
          controller.signal,
        );
      }
    }
  }

  async function consumeOnce(reconnecting: boolean): Promise<boolean> {
    const headers = new Headers({
      Accept: "text/event-stream",
      "Last-Event-ID": String(cursor),
    });
    const response = await fetchImplementation(withAfter(options.url, cursor), {
      method: "GET",
      headers,
      credentials: options.credentials ?? "same-origin",
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new RouteDeckStreamError(
          "stream_session_not_found",
          "The RouteDeck event session no longer exists.",
          { retryable: false, status: response.status },
        );
      }
      if (response.status === 410) {
        throw new RouteDeckStreamError(
          "stream_session_expired",
          "The RouteDeck event session has expired.",
          { retryable: false, status: response.status },
        );
      }
      throw new RouteDeckStreamError(
        "stream_http_error",
        `RouteDeck event stream failed with ${response.status}.`,
        { status: response.status },
      );
    }
    if (!response.headers.get("content-type")?.startsWith("text/event-stream")) {
      throw new RouteDeckStreamError(
        "stream_content_type_invalid",
        "RouteDeck event stream did not return text/event-stream.",
      );
    }
    if (!response.body) {
      throw new RouteDeckStreamError(
        "stream_body_missing",
        "RouteDeck event stream returned no body.",
      );
    }
    options.onOpen?.({ after: cursor, reconnecting });
    for await (const frame of parseSseBody(response.body)) {
      if (frame.event === "stream_reset_required") {
        options.onReset(decodeReset(frame));
        return true;
      }
      if (frame.event === null) continue;
      if (frame.id === null) {
        throw new RouteDeckStreamError(
          "stream_cursor_missing",
          "RouteDeck data events require an SSE id.",
        );
      }
      let decoded: unknown;
      try {
        decoded = JSON.parse(frame.data);
      } catch (error) {
        throw new RouteDeckStreamError(
          "stream_data_invalid",
          "RouteDeck SSE data is not valid JSON.",
          { cause: error },
        );
      }
      const event = decodeEvent(decoded);
      const frameCursor = parseCursor(frame.id, "$sse.id");
      if (event.cursor !== frameCursor || event.event_type !== frame.event) {
        throw new RouteDeckStreamError(
          "stream_envelope_mismatch",
          "RouteDeck SSE fields do not match the typed event envelope.",
        );
      }
      cursor = event.cursor;
      options.onEvent(event);
    }
    return false;
  }

  return {
    close() {
      controller.abort();
    },
    done,
  };
}

export async function* parseSseBody(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<ParsedSseFrame> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replaceAll("\r\n", "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const frame = parseFrame(raw);
        if (frame !== null) yield frame;
        boundary = buffer.indexOf("\n\n");
      }
    }
    buffer = (buffer + decoder.decode()).replaceAll("\r\n", "\n").replaceAll("\r", "\n");
    if (buffer.trim()) {
      const frame = parseFrame(buffer);
      if (frame !== null) yield frame;
    }
  } finally {
    reader.releaseLock();
  }
}

function parseFrame(raw: string): ParsedSseFrame | null {
  let id: string | null = null;
  let event: string | null = null;
  const data: string[] = [];
  for (const line of raw.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    const rawValue = separator === -1 ? "" : line.slice(separator + 1);
    const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;
    if (field === "id") id = value;
    else if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  if (event === null && data.length === 0) return null;
  return { id, event, data: data.join("\n") };
}

function decodeReset(frame: ParsedSseFrame): RouteDeckStreamReset {
  if (frame.id !== null) {
    throw new RouteDeckStreamError(
      "stream_reset_cursor_forbidden",
      "stream_reset_required must not advance the event cursor.",
    );
  }
  let value: unknown;
  try {
    value = JSON.parse(frame.data);
  } catch (error) {
    throw new RouteDeckStreamError(
      "stream_reset_invalid",
      "stream_reset_required data is invalid.",
      { cause: error },
    );
  }
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new RouteDeckStreamError(
      "stream_reset_invalid",
      "stream_reset_required data must be an object.",
    );
  }
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record).sort();
  const expected = ["event_type", "requested_after", "retained_from_cursor"];
  if (keys.length !== expected.length || keys.some((key, index) => key !== expected[index])) {
    throw new RouteDeckStreamError(
      "stream_reset_invalid",
      "stream_reset_required contains undeclared fields.",
    );
  }
  if (record.event_type !== "stream_reset_required") {
    throw new RouteDeckStreamError(
      "stream_reset_invalid",
      "stream_reset_required has the wrong event type.",
    );
  }
  return {
    event_type: "stream_reset_required",
    requested_after: parseCursor(record.requested_after, "$sse.reset.requested_after"),
    retained_from_cursor:
      record.retained_from_cursor === null
        ? null
        : parseCursor(
            record.retained_from_cursor,
            "$sse.reset.retained_from_cursor",
          ),
  };
}

function parseCursor(value: unknown, path: string): number {
  const cursor =
    typeof value === "string" && value !== ""
      ? Number(value)
      : typeof value === "number"
        ? value
        : Number.NaN;
  if (!Number.isInteger(cursor) || cursor < 0 || (typeof value === "string" && String(cursor) !== value)) {
    throw new RouteDeckContractError(path, "expected a canonical non-negative integer");
  }
  return cursor;
}

function withAfter(url: string, cursor: number): string {
  if (url.includes("?")) {
    throw new RouteDeckContractError(
      "$sse.url",
      "event stream URL must not contain an existing query",
    );
  }
  return `${url}?after=${cursor}`;
}

function waitForReconnect(milliseconds: number, signal: AbortSignal): Promise<void> {
  if (!Number.isFinite(milliseconds) || milliseconds < 0) {
    throw new RouteDeckContractError(
      "$sse.reconnectDelayMs",
      "expected a non-negative finite number",
    );
  }
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }
    const timeout = setTimeout(resolve, milliseconds);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timeout);
        resolve();
      },
      { once: true },
    );
  });
}
