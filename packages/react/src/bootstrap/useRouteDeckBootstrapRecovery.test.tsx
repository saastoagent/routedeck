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

  it("exposes no action while retained navigation recovery is in progress", async () => {
    const harness = createStoreHarness({
      syncStatus: "navigating",
      pendingNavigation: {
        requestId: "navigation-1",
        fingerprint: "fingerprint-1",
        intent: { kind: "open_path", path: "/products/public" },
      },
    });

    await renderRecoveryHook(harness.store);

    expect(currentState()).toMatchObject({
      phase: "loading",
      syncStatus: "navigating",
    });
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
  const store: RouteDeckStore = {
    getState: () => state,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    bootstrap: actions.bootstrap,
    dispatch: async () => {
      throw new Error("Unexpected dispatch.");
    },
    acceptReview: async () => {
      throw new Error("Unexpected review acceptance.");
    },
    rejectReview: async () => {
      throw new Error("Unexpected review rejection.");
    },
    inspect: async () => {
      throw new Error("Unexpected inspection.");
    },
    receiveEvent() {},
    resync: actions.resync,
    synchronizeTo: async () => undefined,
    openPath: async () => undefined,
    back() {},
    forward() {},
    cancel: async () => undefined,
    retrySessionCreate: actions.retrySessionCreate,
    startNewSession: actions.startNewSession,
    retryNavigation: actions.retryNavigation,
    abandonNavigation: actions.abandonNavigation,
    dispose() {},
  };
  return { store, setState, actions };
}
