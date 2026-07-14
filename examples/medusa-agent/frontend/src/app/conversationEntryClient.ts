import { AgentChatError } from "@routedeck/core";

export interface MedusaConversationEntryRequest {
  request_id: string;
  expected_session_version: number;
}

export interface MedusaConversationEntryResult {
  sessionVersion: number;
  projectionVersion: number;
}

export async function startMedusaConversation(
  request: MedusaConversationEntryRequest,
  options: { baseUrl?: string; fetch?: typeof fetch } = {},
): Promise<MedusaConversationEntryResult> {
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
  if (
    !request.request_id ||
    !Number.isInteger(request.expected_session_version) ||
    request.expected_session_version < 0
  ) {
    throw new AgentChatError(
      "conversation_entry_invalid",
      "The conversation entry request is invalid.",
    );
  }
  const response = await fetcher(`${baseUrl}/conversation/entry`, {
    method: "POST",
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new AgentChatError(
      "conversation_entry_failed",
      "The Medusa conversation could not be started.",
      response.status,
    );
  }
  const payload: unknown = await response.json();
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return invalidEntry();
  }
  const value = payload as Record<string, unknown>;
  if (
    !Array.isArray(value.turns) ||
    !isVersion(value.session_version) ||
    !isVersion(value.projection_version) ||
    Object.keys(value).some(
      (key) =>
        key !== "turns" &&
        key !== "session_version" &&
        key !== "projection_version",
    )
  ) {
    return invalidEntry();
  }
  return Object.freeze({
    sessionVersion: value.session_version,
    projectionVersion: value.projection_version,
  });
}

function isVersion(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function invalidEntry(): never {
  throw new AgentChatError(
    "conversation_entry_contract_invalid",
    "The Medusa conversation entry contract is invalid.",
  );
}
