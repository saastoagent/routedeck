// @vitest-environment jsdom

import { StrictMode, act } from "react";
import { createRoot, type Root } from "react-dom/client";
import {
  createInitialRouteDeckState,
  type RouteDeckClientState,
  type RouteDeckStore,
} from "@routedeck/core";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  useRouteDeckBootstrapRecovery,
  type RouteDeckBootstrapRecoveryState,
} from "./useRouteDeckBootstrapRecovery";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

let root: Root | null = null;

afterEach(() => {
  if (root !== null) {
    act(() => root?.unmount());
    root = null;
  }
  document.body.replaceChildren();
});

describe("useRouteDeckBootstrapRecovery", () => {
  it("starts an idle store exactly once under StrictMode", async () => {
    const harness = createStoreHarness({ syncStatus: "idle" });
    harness.actions.bootstrap.mockImplementation(async () => {
      harness.setState({ syncStatus: "bootstrapping" });
    });

    await renderRecoveryHook(harness.store, true);

    expect(harness.actions.bootstrap).toHaveBeenCalledOnce();
    expect(currentState().phase).toBe("loading");
  });

  it("keeps an in-flight initial session create in the loading phase", async () => {
    const harness = createStoreHarness({
      syncStatus: "bootstrapping",
      pendingBootstrap: { kind: "session_create" },
    });

    await renderRecoveryHook(harness.store);

    expect(currentState()).toMatchObject({
      phase: "loading",
      syncStatus: "bootstrapping",
    });
  });

  it.each([
    {
      label: "uncertain session creation",
      state: {
        pendingBootstrap: { kind: "session_create" as const },
      },
      reason: "session_create",
      actions: ["retry_session_create", "start_new_session"],
    },
    {
      label: "expired resume",
      state: {
        pendingBootstrap: { kind: "resume_expired" as const, status: 410 as const },
      },
      reason: "resume_expired",
      actions: ["start_new_session"],
    },
    {
      label: "missing resume",
      state: {
        pendingBootstrap: { kind: "resume_missing" as const, status: 404 as const },
      },
      reason: "resume_missing",
      actions: ["start_new_session"],
    },
    {
      label: "contract-mismatched resume",
      state: {
        pendingBootstrap: {
          kind: "resume_contract_mismatch" as const,
          status: 409 as const,
        },
      },
      reason: "resume_contract_mismatch",
      actions: ["start_new_session"],
    },
    {
      label: "uncertain navigation",
      state: {
        pendingNavigation: {
          requestId: "private-navigation-request",
          fingerprint: "private-navigation-fingerprint",
          intent: { kind: "open_path" as const, path: "/products/public" },
        },
      },
      reason: "navigation",
      actions: ["retry_navigation", "abandon_navigation"],
    },
    {
      label: "ordinary synchronization failure",
      state: {},
      reason: "resync",
      actions: ["resync"],
    },
  ])("exposes only legal actions for $label", async ({
    state,
    reason,
    actions,
  }) => {
    const harness = createStoreHarness({
      syncStatus: "error",
      error: { code: "bootstrap_failed", message: "Bootstrap failed." },
      ...state,
    });

    await renderRecoveryHook(harness.store);

    const recovery = currentState();
    expect(recovery.phase).toBe("recovery");
    if (recovery.phase !== "recovery") throw new Error("Expected recovery state");
    expect(recovery.reason).toBe(reason);
    expect(recovery.actions.map((action) => action.kind)).toEqual(actions);
    expect(JSON.stringify(recovery)).not.toContain("private-navigation-request");
    expect(JSON.stringify(recovery)).not.toContain("private-navigation-fingerprint");
  });

  it("invokes the exact store action and returns ready after recovery", async () => {
    const harness = createStoreHarness({
      syncStatus: "error",
      pendingNavigation: {
        requestId: "navigation-1",
        fingerprint: "fingerprint-1",
        intent: { kind: "open_path", path: "/products/public" },
      },
    });
    harness.actions.abandonNavigation.mockImplementation(async () => {
      harness.setState({
        syncStatus: "live",
        pendingNavigation: null,
        error: null,
      });
    });
    await renderRecoveryHook(harness.store);

    const recovery = currentState();
    if (recovery.phase !== "recovery") throw new Error("Expected recovery state");
    const abandon = recovery.actions.find(
      (action) => action.kind === "abandon_navigation",
    );
    if (abandon === undefined) throw new Error("Missing abandon action");
    await act(async () => abandon.run());

    expect(harness.actions.abandonNavigation).toHaveBeenCalledOnce();
    expect(currentState().phase).toBe("ready");
  });

  it("leaves duplicate-action semantics to the core store", async () => {
    const harness = createStoreHarness({ syncStatus: "error" });
    await renderRecoveryHook(harness.store);

    const recovery = currentState();
    if (recovery.phase !== "recovery") throw new Error("Expected recovery state");
    const resync = recovery.actions.find((action) => action.kind === "resync");
    if (resync === undefined) throw new Error("Missing resync action");
    await act(async () => {
      await Promise.all([resync.run(), resync.run()]);
    });

    expect(harness.actions.resync).toHaveBeenCalledTimes(2);
  });

  it("reports the store's safe failure when a recovery action fails", async () => {
    const harness = createStoreHarness({ syncStatus: "error" });
    harness.actions.resync.mockImplementation(async () => {
      harness.setState({
        syncStatus: "error",
        error: {
          code: "session_unavailable",
          message: "The RouteDeck session is unavailable.",
        },
      });
      throw new Error("private transport detail");
    });
    await renderRecoveryHook(harness.store);

    const recovery = currentState();
    if (recovery.phase !== "recovery") throw new Error("Expected recovery state");
    const resync = recovery.actions.find((action) => action.kind === "resync");
    if (resync === undefined) throw new Error("Missing resync action");
    await act(async () => resync.run());

    const failed = currentState();
    if (failed.phase !== "recovery") throw new Error("Expected recovery state");
    expect(failed.error).toEqual({
      code: "session_unavailable",
      message: "The RouteDeck session is unavailable.",
    });
    expect(JSON.stringify(failed)).not.toContain("private transport detail");
  });

  it("does not let an action failure mask newer canonical store state", async () => {
    const harness = createStoreHarness({ syncStatus: "error", error: null });
    harness.actions.resync.mockRejectedValue(new Error("private failure"));
    await renderRecoveryHook(harness.store);

    const recovery = currentState();
    if (recovery.phase !== "recovery") throw new Error("Expected recovery state");
    const resync = recovery.actions.find((action) => action.kind === "resync");
    if (resync === undefined) throw new Error("Missing resync action");
    await act(async () => resync.run());
    const failed = currentState();
    if (failed.phase !== "recovery") throw new Error("Expected recovery state");
    expect(failed.error?.code).toBe("bootstrap_recovery_failed");

    await act(async () => {
      harness.setState({
        error: {
          code: "authoritative_store_failure",
          message: "The authoritative store state changed.",
        },
      });
    });

    const updated = currentState();
    if (updated.phase !== "recovery") throw new Error("Expected recovery state");
    expect(updated.error).toEqual({
      code: "authoritative_store_failure",
      message: "The authoritative store state changed.",
    });
  });

  it("exposes no recovery action after disposal", async () => {
    const harness = createStoreHarness({ syncStatus: "disposed" });

    await renderRecoveryHook(harness.store);

    expect(currentState()).toMatchObject({ phase: "disposed", actions: [] });
  });
});

let observedState: RouteDeckBootstrapRecoveryState | null = null;

async function renderRecoveryHook(
  store: RouteDeckStore,
  strict = false,
): Promise<void> {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  function Probe() {
    observedState = useRouteDeckBootstrapRecovery(store);
    return null;
  }
  await act(async () => {
    root?.render(strict ? <StrictMode><Probe /></StrictMode> : <Probe />);
  });
}

function currentState(): RouteDeckBootstrapRecoveryState {
  if (observedState === null) throw new Error("The hook did not render.");
  return observedState;
}

function createStoreHarness(initial: Partial<RouteDeckClientState>) {
  let state: RouteDeckClientState = Object.freeze({
    ...createInitialRouteDeckState(),
    ...initial,
  });
  const listeners = new Set<() => void>();
  const setState = (next: Partial<RouteDeckClientState>) => {
    state = Object.freeze({ ...state, ...next });
    for (const listener of listeners) listener();
  };
  const actions = {
    bootstrap: vi.fn(async () => undefined),
    retrySessionCreate: vi.fn(async () => undefined),
    startNewSession: vi.fn(async () => undefined),
    retryNavigation: vi.fn(async () => undefined),
    abandonNavigation: vi.fn(async () => undefined),
    resync: vi.fn(async () => undefined),
  };
  const store = {
    getState: () => state,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    ...actions,
  } as unknown as RouteDeckStore;
  return { store, setState, actions };
}
