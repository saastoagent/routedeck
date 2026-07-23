import { describe, expect, it, vi } from "vitest";

import type { RouteDeckClient } from "../client/client";
import type { RouteDeckEventConnection } from "../client/sse";
import type {
  RouteDeckDispatchResult,
  RouteDeckInspection,
  RouteDeckProjection,
} from "../contracts/decode";
import { RouteDeckOutcomeUnknownError } from "../client/errors";
import {
  createRouteDeckStore,
  runRouteDeckBootstrapRecoveryAction,
  selectRouteDeckBootstrapRecovery,
} from "../index";
import { createInitialRouteDeckState } from "./state";

describe("RouteDeck bootstrap recovery", () => {
  it("selects and runs the retained session-create recovery owned by the store", async () => {
    const projection = projectionFixture();
    const requests: Array<{ request_id: string }> = [];
    const client = clientFixture({
      createSession: vi.fn(async (request) => {
        requests.push(request);
        if (requests.length === 1) {
          throw new RouteDeckOutcomeUnknownError(
            request.request_id,
            "The session-create response was lost.",
          );
        }
        return projection;
      }),
    });
    const store = createRouteDeckStore({
      client,
      bootstrapMode: "create",
      createRequestId: () => "session-create-1",
    });

    await expect(store.bootstrap()).rejects.toBeInstanceOf(
      RouteDeckOutcomeUnknownError,
    );
    expect(selectRouteDeckBootstrapRecovery(store.getState())).toEqual({
      phase: "recovery",
      reason: "session_create",
      actionKinds: ["retry_session_create", "start_new_session"],
    });

    await runRouteDeckBootstrapRecoveryAction(store, "retry_session_create");

    expect(requests).toHaveLength(2);
    expect(requests[1]).toBe(requests[0]);
    expect(selectRouteDeckBootstrapRecovery(store.getState())).toEqual({
      phase: "ready",
    });
    store.dispose();
  });

  it("does not expose retained navigation actions while recovery is in progress", () => {
    const state = {
      ...createInitialRouteDeckState(),
      syncStatus: "navigating" as const,
      pendingNavigation: {
        requestId: "private-request",
        fingerprint: "private-fingerprint",
        intent: { kind: "open_path" as const, path: "/products/public" },
      },
    };

    expect(selectRouteDeckBootstrapRecovery(state)).toEqual({
      phase: "loading",
    });
  });

  it.each([
    {
      label: "expired resume",
      state: {
        syncStatus: "error" as const,
        pendingBootstrap: { kind: "resume_expired" as const, status: 410 as const },
      },
      selection: {
        phase: "recovery",
        reason: "resume_expired",
        actionKinds: ["start_new_session"],
      },
    },
    {
      label: "missing resume",
      state: {
        syncStatus: "error" as const,
        pendingBootstrap: { kind: "resume_missing" as const, status: 404 as const },
      },
      selection: {
        phase: "recovery",
        reason: "resume_missing",
        actionKinds: ["start_new_session"],
      },
    },
    {
      label: "contract-mismatched resume",
      state: {
        syncStatus: "error" as const,
        pendingBootstrap: {
          kind: "resume_contract_mismatch" as const,
          status: 409 as const,
        },
      },
      selection: {
        phase: "recovery",
        reason: "resume_contract_mismatch",
        actionKinds: ["start_new_session"],
      },
    },
    {
      label: "retained navigation",
      state: {
        syncStatus: "error" as const,
        pendingNavigation: {
          requestId: "private-request",
          fingerprint: "private-fingerprint",
          intent: { kind: "open_path" as const, path: "/products/public" },
        },
      },
      selection: {
        phase: "recovery",
        reason: "navigation",
        actionKinds: ["retry_navigation", "abandon_navigation"],
      },
    },
    {
      label: "generic synchronization error",
      state: { syncStatus: "error" as const },
      selection: {
        phase: "recovery",
        reason: "resync",
        actionKinds: ["resync"],
      },
    },
  ])("owns the legal recovery descriptor for $label", ({ state, selection }) => {
    const selected = selectRouteDeckBootstrapRecovery({
      ...createInitialRouteDeckState(),
      ...state,
    });

    expect(selected).toEqual(selection);
    expect(JSON.stringify(selected)).not.toContain("private-request");
    expect(JSON.stringify(selected)).not.toContain("private-fingerprint");
  });

  it("rejects an action that is not legal for the current store state", async () => {
    const client = clientFixture({ getSession: vi.fn(async () => projectionFixture()) });
    const store = createRouteDeckStore({ client, bootstrapMode: "resume" });
    await store.bootstrap();

    await expect(
      runRouteDeckBootstrapRecoveryAction(store, "start_new_session"),
    ).rejects.toMatchObject({
      code: "bootstrap_recovery_action_unavailable",
    });
    store.dispose();
  });
});

function clientFixture(
  overrides: Partial<RouteDeckClient> = {},
): RouteDeckClient {
  return {
    getFrontendContract: async () => {
      throw new Error("Unexpected frontend contract request.");
    },
    createSession: async () => {
      throw new Error("Unexpected session creation.");
    },
    getSession: async () => {
      throw new Error("Unexpected session load.");
    },
    navigate: async () => {
      throw new Error("Unexpected navigation.");
    },
    dispatch: async (): Promise<RouteDeckDispatchResult> => {
      throw new Error("Unexpected dispatch.");
    },
    acceptReview: async (): Promise<RouteDeckDispatchResult> => {
      throw new Error("Unexpected review acceptance.");
    },
    rejectReview: async (): Promise<RouteDeckDispatchResult> => {
      throw new Error("Unexpected review rejection.");
    },
    inspect: async (): Promise<RouteDeckInspection> => {
      throw new Error("Unexpected inspection.");
    },
    connectEvents: (options): RouteDeckEventConnection => {
      options.onOpen?.({ after: options.after, reconnecting: false });
      return {
        close() {},
        done: new Promise<void>(() => undefined),
      };
    },
    privateForms: {
      load: async () => {
        throw new Error("Unexpected private-form load.");
      },
      save: async () => {
        throw new Error("Unexpected private-form save.");
      },
    },
    ...overrides,
  };
}

function projectionFixture(): RouteDeckProjection {
  const location = { node_id: "home", route_params: [] };
  return {
    current: location,
    diagnostics: {
      schema_version: 1,
      navgraph_version: "test-navgraph-v1",
      current_node_id: "home",
      declared_provider_ids: [],
    },
    entities: [],
    event_cursor: 0,
    failure: null,
    interaction: { phase: "idle", owner: null },
    legal_operations: [],
    suggested_actions: [],
    navigation: {
      current: location,
      current_entry_id: 1,
      route_template: "/",
      resume_handle: null,
      can_back: false,
      can_forward: false,
      can_cancel: false,
      back_node_id: null,
      forward_node_id: null,
      cancel_target_node_id: null,
    },
    projection_version: 1,
    session_version: 1,
    status: { code: "ready", message: null },
    surfaces: {
      active: { surface_id: "test.active", component: "test.active", props: [] },
      detail: [],
      diagnostic: [],
      error: [],
      form: [],
      frame: [],
      peer: [],
      review: [],
      status: [],
    },
  };
}
