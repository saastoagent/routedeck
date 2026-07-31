import {
  AgentChatError,
  type AgentAssistantTurnRequest,
  type AgentChatRequest,
  type AgentHistoryTurn,
  type AgentStreamEvent,
} from "./types";
import { decodeFailureEnvelope } from "../contracts/decode";
import {
  generatedObjectDescriptors,
  type GeneratedObjectDescriptor,
} from "../contracts/generatedRuntime";
import strictJsonDecoders from "../contracts/json";

const { expectRecord } = strictJsonDecoders;

interface SseFrame {
  event: string;
  data: unknown;
}

export async function* parseAgentSse(
  body: ReadableStream<Uint8Array>,
): AsyncIterable<AgentStreamEvent> {
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
        if (frame !== null) yield decodeEvent(frame.event, frame.data);
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
      "The agent stream ended with an incomplete event.",
    );
  }
}

export function decodeHistoryTurn(
  value: unknown,
  path: string,
): AgentHistoryTurn {
  const turn = contractRecord(
    value,
    path,
    generatedObjectDescriptors.PublicConversationTurn,
  );
  const role = stringValue(turn.role, `${path}.role`);
  if (role !== "user" && role !== "assistant") invalid(`${path}.role`);
  return {
    turn_id: stringValue(turn.turn_id, `${path}.turn_id`),
    request_id:
      turn.request_id === null
        ? null
        : stringValue(turn.request_id, `${path}.request_id`, true),
    role,
    content: stringValue(turn.content, `${path}.content`, true),
  };
}

export function validateAgentChatRequest(request: AgentChatRequest): void {
  requestIdValue(request.request_id, "request.request_id");
  stringValue(request.message, "request.message");
  integerValue(request.expected_session_version, "request.expected_session_version");
}

export function validateAgentAssistantTurnRequest(
  request: AgentAssistantTurnRequest,
): void {
  requestIdValue(request.request_id, "request.request_id");
  integerValue(
    request.expected_session_version,
    "request.expected_session_version",
  );
}

export async function agentResponseError(
  response: Response,
): Promise<AgentChatError> {
  try {
    const failure = decodeFailureEnvelope(await response.json()).failure;
    return new AgentChatError(
      failure.code,
      failure.public_message,
      response.status,
      response.status >= 500 && response.status <= 599
        ? "unknown"
        : "rejected",
    );
  } catch {
    throw new AgentChatError(
      "chat_contract_invalid",
      "The agent conversation error contract is invalid.",
      response.status,
      response.status >= 500 && response.status <= 599
        ? "unknown"
        : "rejected",
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
      "The agent stream returned an invalid event frame.",
    );
  }
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    throw new AgentChatError(
      "stream_data_invalid",
      "The agent stream returned invalid JSON.",
    );
  }
}

function decodeEvent(event: string, value: unknown): AgentStreamEvent {
  switch (event) {
    case "stream_start": {
      const data = contractRecord(
        value,
        `event:${event}`,
        generatedObjectDescriptors.ConversationStreamStartPayload,
      );
      return {
        type: event,
        request_id: requestIdValue(data.request_id, `${event}.request_id`),
        session_version: versionValue(
          data.session_version,
          `${event}.session_version`,
        ),
      };
    }
    case "conversation_snapshot": {
      const data = contractRecord(
        value,
        `event:${event}`,
        generatedObjectDescriptors.ConversationSnapshotPayload,
      );
      if (!Array.isArray(data.turns)) invalid(`${event}.turns`);
      return {
        type: event,
        turns: data.turns.map((turn, index) =>
          decodeHistoryTurn(turn, `${event}.turns[${index}]`),
        ),
      };
    }
    case "user_message": {
      const data = contractRecord(
        value,
        `event:${event}`,
        generatedObjectDescriptors.ConversationUserMessagePayload,
      );
      return {
        type: event,
        content: stringValue(data.content, `${event}.content`),
        request_id: requestIdValue(data.request_id, `${event}.request_id`),
        turn_id: stringValue(data.turn_id, `${event}.turn_id`),
      };
    }
    case "assistant_delta": {
      const data = contractRecord(
        value,
        `event:${event}`,
        generatedObjectDescriptors.ConversationAssistantDeltaPayload,
      );
      return {
        type: event,
        content: stringValue(data.content, `${event}.content`),
        request_id: requestIdValue(data.request_id, `${event}.request_id`),
      };
    }
    case "assistant_reset": {
      const data = contractRecord(
        value,
        `event:${event}`,
        generatedObjectDescriptors.ConversationAssistantResetPayload,
      );
      return {
        type: event,
        request_id: requestIdValue(data.request_id, `${event}.request_id`),
      };
    }
    case "assistant_end": {
      const data = contractRecord(
        value,
        `event:${event}`,
        generatedObjectDescriptors.ConversationAssistantEndPayload,
      );
      return {
        type: event,
        request_id: requestIdValue(data.request_id, `${event}.request_id`),
        session_version: versionValue(
          data.session_version,
          `${event}.session_version`,
        ),
        projection_version: versionValue(
          data.projection_version,
          `${event}.projection_version`,
        ),
        turn_id: stringValue(data.turn_id, `${event}.turn_id`),
      };
    }
    case "review_required": {
      const data = contractRecord(
        value,
        `event:${event}`,
        generatedObjectDescriptors.ConversationReviewRequiredPayload,
      );
      return {
        type: event,
        status: literalValue(
          data.status,
          "requires_review",
          `${event}.status`,
        ),
        operation_id: stringValue(data.operation_id, `${event}.operation_id`),
        review_id: stringValue(data.review_id, `${event}.review_id`),
        expires_at: stringValue(data.expires_at, `${event}.expires_at`),
      };
    }
    case "chat_error": {
      const data = contractRecord(
        value,
        `event:${event}`,
        generatedObjectDescriptors.ConversationChatErrorPayload,
      );
      return {
        type: event,
        code: stringValue(data.code, `${event}.code`),
        message: stringValue(data.message, `${event}.message`),
      };
    }
    case "stream_end": {
      const data = contractRecord(
        value,
        `event:${event}`,
        generatedObjectDescriptors.ConversationStreamEndPayload,
      );
      return {
        type: event,
        request_id: requestIdValue(data.request_id, `${event}.request_id`),
        status: streamStatus(data.status, `${event}.status`),
      };
    }
    default:
      throw new AgentChatError(
        "stream_event_unknown",
        `The agent stream returned unknown event ${event}.`,
      );
  }
}

function contractRecord(
  value: unknown,
  path: string,
  descriptor: GeneratedObjectDescriptor,
): Record<string, unknown> {
  try {
    return expectRecord(value, path, descriptor);
  } catch {
    invalid(path);
  }
}

function stringValue(value: unknown, path: string, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && !value)) invalid(path);
  return value;
}

function requestIdValue(value: unknown, path: string): string {
  const requestId = stringValue(value, path);
  if (Array.from(requestId).length > 256) invalid(path);
  return requestId;
}

function integerValue(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    invalid(path);
  }
  return value;
}

function versionValue(value: unknown, path: string): number {
  const version = integerValue(value, path);
  if (!Number.isSafeInteger(version)) invalid(path);
  return version;
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
  | "rejected"
  | "turn_interrupted"
  | "outcome_unknown" {
  if (
    value !== "completed" &&
    value !== "requires_review" &&
    value !== "rejected" &&
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
    `The agent conversation contract is invalid at ${path}.`,
  );
}
