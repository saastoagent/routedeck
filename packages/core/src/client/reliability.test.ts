import { describe, expect, it } from "vitest";

import { createRouteDeckClient } from "./client";
import { RouteDeckHttpError, RouteDeckOutcomeUnknownError } from "./errors";

const DISPATCH = {
  operation_id: "cart.add",
  request_id: "request-stable",
  expected_session_version: 7,
  arguments: { variant_ref: "variant-1", quantity: 1 },
};

function typedOperationResult(
  disposition: "needs_input" | "blocked" | "external_outcome_unknown",
) {
  const external = disposition === "external_outcome_unknown";
  return {
    disposition,
    operation_id: DISPATCH.operation_id,
    request_id: DISPATCH.request_id,
    session_version: 8,
    projection_version: 8,
    evidence: {
      source: "surface",
      phases: ["received", "state_committed", "completed"],
      attempt_id: "attempt-terminal",
      request_fingerprint: "fingerprint-terminal",
      delivery_phase: external ? "possibly_sent" : "not_sent",
      result_id: null,
      result_fingerprint: null,
    },
    review: null,
    outcome: null,
    failure: {
      kind: external ? "external_outcome_unknown" : "guard",
      code: external ? "order_outcome_unknown" : "buyer_input_required",
      phase: external ? "external_call" : "guard",
      correlation_id: "correlation-terminal",
      operation_id: DISPATCH.operation_id,
      request_id: DISPATCH.request_id,
      public_message: external
        ? "Order status must be reconciled."
        : "Buyer input is required.",
      recovery_directive: external ? "reconcile_unknown_order" : null,
      safe_details: {
        affected_capability: null,
        provider: null,
        provider_code: null,
        http_status: null,
        delivery_phase: external ? "possibly_sent" : null,
      },
    },
  };
}

describe("RouteDeck mutation failure classification", () => {
  it("marks a lost transport response as outcome unknown with the request id", async () => {
    const client = createRouteDeckClient({
      baseUrl: "https://routedeck.test",
      fetch: async () => {
        throw new TypeError("connection closed");
      },
    });

    await expect(client.dispatch(DISPATCH)).rejects.toMatchObject({
      code: "operation_outcome_unknown",
      requestId: "request-stable",
    } satisfies Partial<RouteDeckOutcomeUnknownError>);
  });

  it("keeps a received HTTP rejection distinct from outcome unknown", async () => {
    const client = createRouteDeckClient({
      baseUrl: "https://routedeck.test",
      fetch: async () =>
        new Response("{}", {
          status: 409,
          headers: { "content-type": "application/json" },
        }),
    });

    await expect(client.dispatch(DISPATCH)).rejects.toBeInstanceOf(
      RouteDeckHttpError,
    );
  });

  it.each([
    [422, "needs_input"],
    [409, "blocked"],
    [409, "external_outcome_unknown"],
  ] as const)(
    "decodes a typed %s operation result with %s disposition",
    async (status, disposition) => {
      const client = createRouteDeckClient({
        baseUrl: "https://routedeck.test",
        fetch: async () =>
          new Response(JSON.stringify(typedOperationResult(disposition)), {
            status,
            headers: { "content-type": "application/json" },
          }),
      });

      await expect(client.dispatch(DISPATCH)).resolves.toMatchObject({
        disposition,
        request_id: DISPATCH.request_id,
        session_version: 8,
      });
    },
  );

  it("retains the exact request after a received server failure", async () => {
    const client = createRouteDeckClient({
      baseUrl: "https://routedeck.test",
      fetch: async () =>
        new Response(
          JSON.stringify(typedOperationResult("external_outcome_unknown")),
          {
            status: 500,
            headers: { "content-type": "application/json" },
          },
        ),
    });

    await expect(client.dispatch(DISPATCH)).rejects.toMatchObject({
      code: "operation_outcome_unknown",
      requestId: "request-stable",
    } satisfies Partial<RouteDeckOutcomeUnknownError>);
  });

  it("retains the exact request after an invalid response contract", async () => {
    const client = createRouteDeckClient({
      baseUrl: "https://routedeck.test",
      fetch: async () =>
        new Response("not-json", {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    });

    await expect(client.dispatch(DISPATCH)).rejects.toMatchObject({
      code: "operation_outcome_unknown",
      requestId: "request-stable",
    } satisfies Partial<RouteDeckOutcomeUnknownError>);
  });
});
