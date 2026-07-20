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
      if (value === null || typeof value !== "object" || Array.isArray(value)) {
        return invalidConversation();
      }
      const payload = value as Record<string, unknown>;
      if (
        !Array.isArray(payload.turns) ||
        Object.keys(payload).some((key) => key !== "turns")
      ) {
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
  });
}


function invalidConversation(): never {
  throw new AgentChatError(
    "chat_contract_invalid",
    "The agent conversation contract is invalid at conversation.",
  );
}

export * from "./types";
