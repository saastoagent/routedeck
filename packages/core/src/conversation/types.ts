export interface AgentChatRequest {
  request_id: string;
  expected_session_version: number;
  message: string;
}

export interface AgentAssistantTurnRequest {
  request_id: string;
  expected_session_version: number;
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
  | { type: "assistant_reset"; request_id: string }
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
        | "rejected"
        | "turn_interrupted"
        | "outcome_unknown";
    };

export interface AgentChatClient {
  stream(
    request: AgentChatRequest,
    signal?: AbortSignal,
  ): AsyncIterable<AgentStreamEvent>;
}

export interface RouteDeckConversationClient {
  loadConversation(signal?: AbortSignal): Promise<readonly AgentHistoryTurn[]>;
}

export interface RouteDeckAgentClient
  extends AgentChatClient,
    RouteDeckConversationClient {
  streamAssistantTurn(
    request: AgentAssistantTurnRequest,
    signal?: AbortSignal,
  ): AsyncIterable<AgentStreamEvent>;
}

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

const SESSION_RECOVERY_CODES = new Set(["session_not_found", "session_expired"]);

export function isRouteDeckConversationSessionRecoveryError(
  error: unknown,
): error is AgentChatError {
  return error instanceof AgentChatError && SESSION_RECOVERY_CODES.has(error.code);
}
