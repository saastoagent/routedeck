import {
  agentResponseError,
  decodeHistoryTurn,
  parseAgentSse,
  validateAgentAssistantTurnRequest,
  validateAgentChatRequest,
} from "./codec";
import {
  AgentChatError,
  type AgentAssistantTurnRequest,
  type AgentChatRequest,
  type RouteDeckAgentClient,
} from "./types";
import {
  decodeConversationRunEnvelope,
  parseConversationRunSse,
  validateConversationRunCursor,
  validateConversationRunRequestId,
} from "./runs";
import { generatedObjectDescriptors } from "../contracts/generatedRuntime";
import strictJsonDecoders from "../contracts/json";

const { expectRecord } = strictJsonDecoders;

export function createRouteDeckAgentClient(
  options: { baseUrl?: string; fetch?: typeof fetch } = {},
): RouteDeckAgentClient {
  const configuredBaseUrl = options.baseUrl ?? "/api/routedeck";
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
      if (!response.ok) throw await agentResponseError(response);
      const value: unknown = await response.json();
      let payload: Record<string, unknown>;
      try {
        payload = expectRecord(
          value,
          "conversation",
          generatedObjectDescriptors.ConversationHistoryEnvelope,
        );
      } catch {
        return invalidConversation();
      }
      if (!Array.isArray(payload.turns)) {
        return invalidConversation();
      }
      return Object.freeze(
        payload.turns.map((turn, index) =>
          Object.freeze(decodeHistoryTurn(turn, `conversation.turns[${index}]`)),
        ),
      );
    },
    async *stream(request: AgentChatRequest, signal?: AbortSignal) {
      validateAgentChatRequest(request);
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
      if (!response.ok) throw await agentResponseError(response);
      if (response.body === null) {
        throw new AgentChatError(
          "stream_body_missing",
          "The agent stream has no response body.",
          response.status,
          "unknown",
        );
      }
      yield* parseAgentSse(response.body);
    },
    async *streamAssistantTurn(
      request: AgentAssistantTurnRequest,
      signal?: AbortSignal,
    ) {
      validateAgentAssistantTurnRequest(request);
      const response = await fetcher(`${baseUrl}/conversation/assistant-turn`, {
        method: "POST",
        credentials: "include",
        headers: {
          Accept: "text/event-stream",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        ...(signal === undefined ? {} : { signal }),
      });
      if (!response.ok) throw await agentResponseError(response);
      if (response.body === null) {
        throw new AgentChatError(
          "stream_body_missing",
          "The agent stream has no response body.",
          response.status,
          "unknown",
        );
      }
      yield* parseAgentSse(response.body);
    },
    async startAssistantRun(
      request: AgentAssistantTurnRequest,
      signal?: AbortSignal,
    ) {
      validateAgentAssistantTurnRequest(request);
      const response = await fetcher(`${baseUrl}/conversation/runs`, {
        method: "POST",
        credentials: "include",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ...request, trigger: "assistant_initiated" }),
        ...(signal === undefined ? {} : { signal }),
      });
      if (!response.ok) throw await agentResponseError(response);
      return decodeConversationRunEnvelope(await response.json());
    },
    async loadConversationRun(requestId: string, signal?: AbortSignal) {
      validateConversationRunRequestId(requestId);
      const response = await fetcher(
        `${baseUrl}/conversation/runs/${encodeURIComponent(requestId)}`,
        {
          method: "GET",
          credentials: "include",
          headers: { Accept: "application/json" },
          ...(signal === undefined ? {} : { signal }),
        },
      );
      if (!response.ok) throw await agentResponseError(response);
      return decodeConversationRunEnvelope(await response.json());
    },
    async *streamConversationRunEvents(
      requestId: string,
      after: number,
      signal?: AbortSignal,
    ) {
      validateConversationRunRequestId(requestId);
      validateConversationRunCursor(after);
      const response = await fetcher(
        `${baseUrl}/conversation/runs/${encodeURIComponent(requestId)}/events?after=${after}`,
        {
          method: "GET",
          credentials: "include",
          headers: { Accept: "text/event-stream" },
          cache: "no-store",
          ...(signal === undefined ? {} : { signal }),
        },
      );
      if (!response.ok) throw await agentResponseError(response);
      if (!response.headers.get("content-type")?.startsWith("text/event-stream")) {
        throw new AgentChatError(
          "conversation_run_stream_content_type_invalid",
          "The conversation run event stream has an invalid content type.",
        );
      }
      if (response.body === null) {
        throw new AgentChatError(
          "conversation_run_stream_body_missing",
          "The conversation run event stream has no response body.",
          response.status,
          "unknown",
        );
      }
      yield* parseConversationRunSse(response.body);
    },
  });
}


function invalidConversation(): never {
  throw new AgentChatError(
    "chat_contract_invalid",
    "The agent conversation contract is invalid at conversation.",
  );
}

export * from "./types";
