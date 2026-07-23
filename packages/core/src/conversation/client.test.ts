import { describe, expect, it, vi } from "vitest";

import {
  createRouteDeckAgentClient,
  isRouteDeckConversationSessionRecoveryError,
} from "./client";
import { AgentChatError } from "./types";

describe("RouteDeck conversation failures", () => {
  it("decodes the canonical RouteDeck failure envelope", async () => {
    const fetcher = vi.fn(async () => canonicalFailureResponse(
      404,
      "session_not_found",
      "The RouteDeck session request could not be completed.",
    ));
    const client = createRouteDeckAgentClient({ fetch: fetcher });

    const failure = await client.loadConversation().catch((error: unknown) => error);

    expect(failure).toMatchObject({
      code: "session_not_found",
      message: "The RouteDeck session request could not be completed.",
      status: 404,
      outcome: "rejected",
    });
    expect(isRouteDeckConversationSessionRecoveryError(failure)).toBe(true);
  });

  it("does not classify an unrelated HTTP error as session recovery", () => {
    const failure = new AgentChatError(
      "conversation_endpoint_missing",
      "The conversation endpoint is unavailable.",
      404,
      "rejected",
    );

    expect(isRouteDeckConversationSessionRecoveryError(failure)).toBe(false);
  });

  it("fails explicitly when the server returns the retired compact envelope", async () => {
    const fetcher = vi.fn(async () => new Response(
      JSON.stringify({
        failure: {
          code: "session_not_found",
          message: "The session is missing.",
        },
      }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    ));
    const client = createRouteDeckAgentClient({ fetch: fetcher });

    await expect(client.loadConversation()).rejects.toMatchObject({
      code: "chat_contract_invalid",
      status: 404,
    });
  });
});

function canonicalFailureResponse(
  status: number,
  code: string,
  publicMessage: string,
): Response {
  return new Response(
    JSON.stringify({
      failure: {
        kind: "persistence",
        code,
        phase: "session_store",
        correlation_id: "conversation-failure-1",
        operation_id: null,
        request_id: null,
        public_message: publicMessage,
        recovery_directive: null,
        safe_details: {
          affected_capability: null,
          provider: null,
          provider_code: null,
          http_status: null,
          delivery_phase: null,
        },
      },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}
