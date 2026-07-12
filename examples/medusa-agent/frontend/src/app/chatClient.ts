export interface AgentChatRequest {
  request_id: string;
  expected_session_version: number;
  message: string;
}

export interface AgentHistoryTurn {
  turn_id: string;
  request_id: string | null;
  role: "user" | "assistant";
  content: string;
}

export interface AgentReviewRequired {
  status: "requires_review";
  operation_id: string;
  review_id: string;
  expires_at: string;
}

export type AgentStreamEvent =
  | {
      type: "stream_start";
      request_id: string;
      session_version: number;
    }
  | { type: "conversation_snapshot"; turns: AgentHistoryTurn[] }
  | {
      type: "user_message";
      content: string;
      request_id: string;
      turn_id: string;
    }
  | { type: "assistant_delta"; content: string; request_id: string }
  | {
      type: "assistant_end";
      request_id: string;
      session_version: number;
      projection_version: number;
      turn_id: string;
    }
  | ({ type: "review_required" } & AgentReviewRequired)
  | { type: "chat_error"; code: string; message: string }
  | {
      type: "stream_end";
      request_id: string;
      status:
        | "completed"
        | "requires_review"
        | "turn_interrupted"
        | "outcome_unknown";
    };

export interface AgentChatClient {
  stream(
    request: AgentChatRequest,
    signal?: AbortSignal,
  ): AsyncIterable<AgentStreamEvent>;
}

export interface AgentConversationClient {
  loadConversation(signal?: AbortSignal): Promise<readonly AgentHistoryTurn[]>;
}

export interface MedusaAgentClient
  extends AgentChatClient,
    AgentConversationClient {}

export type AgentChatFailureOutcome =
  | "not_sent"
  | "rejected"
  | "unknown"
  | "interrupted";

export class AgentChatError extends Error {
  readonly code: string;
  readonly status: number | null;
  readonly outcome: AgentChatFailureOutcome;

  constructor(
    code: string,
    message: string,
    status: number | null = null,
    outcome: AgentChatFailureOutcome = status === null ? "unknown" : "rejected",
  ) {
    super(message);
    this.name = "AgentChatError";
    this.code = code;
    this.status = status;
    this.outcome = outcome;
  }
}

export function createAgentChatClient(
  options: { baseUrl?: string; fetch?: typeof fetch } = {},
): MedusaAgentClient {
  const configuredBaseUrl = options.baseUrl ?? "/api/medusa-agent";
  const baseUrl = configuredBaseUrl.endsWith("/")
    ? configuredBaseUrl.slice(0, -1)
    : configuredBaseUrl;
  const fetcher = options.fetch ?? globalThis.fetch;
  if (typeof fetcher !== "function") {
    throw new AgentChatError(
      "fetch_unavailable",
      "The browser fetch API is unavailable.",
    );
  }
  return Object.freeze({
    async loadConversation(signal?: AbortSignal) {
      const response = await fetcher(`${baseUrl}/conversation`, {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
        ...(signal === undefined ? {} : { signal }),
      });
      if (!response.ok) throw await responseError(response);
      const payload = record(await response.json(), "conversation");
      if (
        !Array.isArray(payload.turns) ||
        Object.keys(payload).some((key) => key !== "turns")
      ) {
        invalid("conversation");
      }
      return Object.freeze(
        payload.turns.map((turn, index) =>
          Object.freeze(decodeHistoryTurn(turn, `conversation.turns[${index}]`)),
        ),
      );
    },
    async *stream(request: AgentChatRequest, signal?: AbortSignal) {
      validateRequest(request);
      const response = await fetcher(`${baseUrl}/chat`, {
        method: "POST",
        credentials: "include",
        headers: {
          Accept: "text/event-stream",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        ...(signal === undefined ? {} : { signal }),
      });
      if (!response.ok) throw await responseError(response);
      if (response.body === null) {
        throw new AgentChatError(
          "stream_body_missing",
          "The buyer-agent stream has no response body.",
          response.status,
          "unknown",
        );
      }
      for await (const frame of parseSse(response.body)) {
        yield decodeEvent(frame.event, frame.data);
      }
    },
  });
}

interface SseFrame {
  event: string;
  data: unknown;
}

async function* parseSse(
  body: ReadableStream<Uint8Array>,
): AsyncIterable<SseFrame> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const result = await reader.read();
      buffer += decoder.decode(result.value, { stream: !result.done });
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const rawFrame = buffer.slice(0, boundary).replaceAll("\r\n", "\n");
        buffer = buffer.slice(boundary + 2);
        const frame = decodeFrame(rawFrame);
        if (frame !== null) yield frame;
        boundary = buffer.indexOf("\n\n");
      }
      if (result.done) break;
    }
  } finally {
    reader.releaseLock();
  }
  if (buffer.trim()) {
    throw new AgentChatError(
      "stream_frame_incomplete",
      "The buyer-agent stream ended with an incomplete event.",
    );
  }
}

function decodeFrame(rawFrame: string): SseFrame | null {
  if (!rawFrame || rawFrame.startsWith(":")) return null;
  let event: string | null = null;
  const dataLines: string[] = [];
  for (const line of rawFrame.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  if (event === null || !event || dataLines.length === 0) {
    throw new AgentChatError(
      "stream_frame_invalid",
      "The buyer-agent stream returned an invalid event frame.",
    );
  }
  let data: unknown;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    throw new AgentChatError(
      "stream_data_invalid",
      "The buyer-agent stream returned invalid JSON.",
    );
  }
  return { event, data };
}

function decodeEvent(event: string, value: unknown): AgentStreamEvent {
  const data = record(value, `event:${event}`);
  switch (event) {
    case "stream_start":
      return {
        type: event,
        request_id: stringValue(data.request_id, `${event}.request_id`),
        session_version: integerValue(
          data.session_version,
          `${event}.session_version`,
        ),
      };
    case "conversation_snapshot": {
      if (!Array.isArray(data.turns)) invalid(`${event}.turns`);
      return {
        type: event,
        turns: data.turns.map((turn, index) =>
          decodeHistoryTurn(turn, `${event}.turns[${index}]`),
        ),
      };
    }
    case "user_message":
      return {
        type: event,
        content: stringValue(data.content, `${event}.content`),
        request_id: stringValue(data.request_id, `${event}.request_id`),
        turn_id: stringValue(data.turn_id, `${event}.turn_id`),
      };
    case "assistant_delta":
      return {
        type: event,
        content: stringValue(data.content, `${event}.content`),
        request_id: stringValue(data.request_id, `${event}.request_id`),
      };
    case "assistant_end":
      return {
        type: event,
        request_id: stringValue(data.request_id, `${event}.request_id`),
        session_version: integerValue(
          data.session_version,
          `${event}.session_version`,
        ),
        projection_version: integerValue(
          data.projection_version,
          `${event}.projection_version`,
        ),
        turn_id: stringValue(data.turn_id, `${event}.turn_id`),
      };
    case "review_required":
      return {
        type: event,
        status: literalValue(
          data.status,
          "requires_review",
          `${event}.status`,
        ),
        operation_id: stringValue(
          data.operation_id,
          `${event}.operation_id`,
        ),
        review_id: stringValue(data.review_id, `${event}.review_id`),
        expires_at: stringValue(data.expires_at, `${event}.expires_at`),
      };
    case "chat_error":
      return {
        type: event,
        code: stringValue(data.code, `${event}.code`),
        message: stringValue(data.message, `${event}.message`),
      };
    case "stream_end":
      return {
        type: event,
        request_id: stringValue(data.request_id, `${event}.request_id`),
        status: streamStatus(data.status, `${event}.status`),
      };
    default:
      throw new AgentChatError(
        "stream_event_unknown",
        `The buyer-agent stream returned unknown event ${event}.`,
      );
  }
}

function decodeHistoryTurn(value: unknown, path: string): AgentHistoryTurn {
  const turn = record(value, path);
  const role = stringValue(turn.role, `${path}.role`);
  if (role !== "user" && role !== "assistant") invalid(`${path}.role`);
  return {
    turn_id: stringValue(turn.turn_id, `${path}.turn_id`),
    request_id:
      turn.request_id === null
        ? null
        : stringValue(turn.request_id, `${path}.request_id`),
    role,
    content: stringValue(turn.content, `${path}.content`, true),
  };
}

function validateRequest(request: AgentChatRequest): void {
  stringValue(request.request_id, "request.request_id");
  stringValue(request.message, "request.message");
  integerValue(request.expected_session_version, "request.expected_session_version");
}

async function responseError(response: Response): Promise<AgentChatError> {
  try {
    const payload = record(await response.json(), "response");
    const failure = record(payload.failure, "response.failure");
    return new AgentChatError(
      stringValue(failure.code, "response.failure.code"),
      stringValue(failure.message, "response.failure.message"),
      response.status,
      response.status >= 500 && response.status <= 599
        ? "unknown"
        : "rejected",
    );
  } catch (error) {
    if (error instanceof AgentChatError) return error;
    return new AgentChatError(
      "chat_request_failed",
      `The buyer-agent request failed with status ${response.status}.`,
      response.status,
      response.status >= 500 && response.status <= 599
        ? "unknown"
        : "rejected",
    );
  }
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    invalid(path);
  }
  return value as Record<string, unknown>;
}

function stringValue(value: unknown, path: string, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && !value)) invalid(path);
  return value;
}

function integerValue(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    invalid(path);
  }
  return value;
}

function literalValue<T extends string>(
  value: unknown,
  expected: T,
  path: string,
): T {
  if (value !== expected) invalid(path);
  return expected;
}

function streamStatus(
  value: unknown,
  path: string,
):
  | "completed"
  | "requires_review"
  | "turn_interrupted"
  | "outcome_unknown" {
  if (
    value !== "completed" &&
    value !== "requires_review" &&
    value !== "turn_interrupted" &&
    value !== "outcome_unknown"
  ) {
    invalid(path);
  }
  return value;
}

function invalid(path: string): never {
  throw new AgentChatError(
    "chat_contract_invalid",
    `The buyer-agent contract is invalid at ${path}.`,
  );
}
