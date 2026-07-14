import type { AgentChatRequest, AgentHistoryTurn } from "@routedeck/core";

export interface AgentConversationMessage {
  id: string;
  requestId: string | null;
  role: "user" | "assistant";
  content: string;
  status: "finalized" | "streaming";
}

export type AgentStreamStatus =
  | "idle"
  | "streaming"
  | "review_required"
  | "error";

export interface AgentPendingRequest {
  readonly requestId: string;
  readonly expectedSessionVersion: number;
  readonly message: string;
}

export function historyMessage(
  turn: AgentHistoryTurn,
): AgentConversationMessage {
  return {
    id: turn.turn_id,
    requestId: turn.request_id,
    role: turn.role,
    content: turn.content,
    status: "finalized",
  };
}

export function pendingRequestFor(
  request: Readonly<AgentChatRequest>,
): AgentPendingRequest {
  return Object.freeze({
    requestId: request.request_id,
    expectedSessionVersion: request.expected_session_version,
    message: request.message,
  });
}
