import { parseSseBody } from "../client/sse";
import { generatedObjectDescriptors } from "../contracts/generatedRuntime";
import strictJsonDecoders from "../contracts/json";
import { AgentChatError, type ConversationRunSnapshot } from "./types";

const { expectRecord } = strictJsonDecoders;

export function decodeConversationRunEnvelope(value: unknown): ConversationRunSnapshot {
  const envelope = exactRecord(
    value,
    "$runEnvelope",
    generatedObjectDescriptors.ConversationRunEnvelope,
  );
  return decodeConversationRun(envelope.run, "$runEnvelope.run");
}

export async function* parseConversationRunSse(
  body: ReadableStream<Uint8Array>,
): AsyncIterable<ConversationRunSnapshot> {
  for await (const frame of parseSseBody(body)) {
    if (frame.event === null) continue;
    if (frame.event !== "conversation_run" || frame.id === null) {
      invalid("$conversationRun.events");
    }
    let value: unknown;
    try {
      value = JSON.parse(frame.data);
    } catch {
      invalid("$conversationRun.events.data");
    }
    const run = decodeConversationRun(value, "$conversationRun.events.data");
    if (String(run.cursor) !== frame.id) {
      invalid("$conversationRun.events.id");
    }
    yield run;
  }
}

export function validateConversationRunCursor(value: number): void {
  integer(value, "$conversationRun.after");
}

export function validateConversationRunRequestId(value: string): void {
  string(value, "$conversationRun.requestId");
}

function decodeConversationRun(value: unknown, path: string): ConversationRunSnapshot {
  const run = exactRecord(
    value,
    path,
    generatedObjectDescriptors.ConversationRunSnapshotPayload,
  );
  const kind = string(run.kind, `${path}.kind`);
  if (kind !== "user_message" && kind !== "assistant_initiated") {
    invalid(`${path}.kind`);
  }
  const stage = string(run.stage, `${path}.stage`);
  if (
    stage !== "starting" &&
    stage !== "awaiting_model" &&
    stage !== "generating" &&
    stage !== "completed" &&
    stage !== "interrupted"
  ) {
    invalid(`${path}.stage`);
  }
  const failure = run.failure === undefined || run.failure === null
    ? null
    : (() => {
        const item = exactRecord(
          run.failure,
          `${path}.failure`,
          generatedObjectDescriptors.ConversationRunFailurePayload,
        );
        return {
          code: string(item.code, `${path}.failure.code`),
          message: string(item.message, `${path}.failure.message`),
        };
      })();
  const snapshot: ConversationRunSnapshot = {
    request_id: string(run.request_id, `${path}.request_id`),
    kind,
    stage,
    cursor: positiveInteger(run.cursor, `${path}.cursor`),
    assistant_content: string(
      run.assistant_content === undefined ? "" : run.assistant_content,
      `${path}.assistant_content`,
      true,
    ),
    user_message: nullableString(
      run.user_message === undefined ? null : run.user_message,
      `${path}.user_message`,
    ),
    user_turn_id: nullableString(
      run.user_turn_id === undefined ? null : run.user_turn_id,
      `${path}.user_turn_id`,
    ),
    session_version: nullableInteger(
      run.session_version === undefined ? null : run.session_version,
      `${path}.session_version`,
    ),
    projection_version: nullableInteger(
      run.projection_version === undefined ? null : run.projection_version,
      `${path}.projection_version`,
    ),
    turn_id: nullableString(
      run.turn_id === undefined ? null : run.turn_id,
      `${path}.turn_id`,
    ),
    failure,
    review: run.review === undefined || run.review === null
      ? null
      : (() => {
          const review = exactRecord(
            run.review,
            `${path}.review`,
            generatedObjectDescriptors.ConversationRunReviewPayload,
          );
          return {
            status: "requires_review" as const,
            expires_at: string(review.expires_at, `${path}.review.expires_at`),
            operation_id: string(review.operation_id, `${path}.review.operation_id`),
            review_id: string(review.review_id, `${path}.review.review_id`),
          };
        })(),
  };
  if (
    (stage === "completed" &&
      (snapshot.session_version === null ||
        snapshot.projection_version === null ||
        failure !== null)) ||
    (stage === "interrupted" && failure === null) ||
    ((stage === "starting" || stage === "awaiting_model" || stage === "generating") &&
      failure !== null)
  ) {
    invalid(path);
  }
  if (
    stage === "completed" &&
    ((snapshot.review === null && snapshot.turn_id === null) ||
      (snapshot.review !== null && snapshot.turn_id !== null))
  ) {
    invalid(path);
  }
  if (
    (kind === "user_message" &&
      ((snapshot.user_message === null) !== (snapshot.user_turn_id === null))) ||
    (kind === "assistant_initiated" &&
      (snapshot.user_message !== null || snapshot.user_turn_id !== null))
  ) {
    invalid(path);
  }
  return Object.freeze(snapshot);
}

function exactRecord(
  value: unknown,
  path: string,
  descriptor: Parameters<typeof expectRecord>[2],
): Record<string, unknown> {
  try {
    return expectRecord(value, path, descriptor);
  } catch {
    invalid(path);
  }
}

function string(value: unknown, path: string, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && !value)) invalid(path);
  return value;
}

function nullableString(value: unknown, path: string): string | null {
  return value === null ? null : string(value, path);
}

function integer(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    invalid(path);
  }
  return value;
}

function positiveInteger(value: unknown, path: string): number {
  const result = integer(value, path);
  if (result < 1) invalid(path);
  return result;
}

function nullableInteger(value: unknown, path: string): number | null {
  return value === null ? null : integer(value, path);
}

function invalid(path: string): never {
  throw new AgentChatError(
    "conversation_run_contract_invalid",
    `The conversation run contract is invalid at ${path}.`,
  );
}
