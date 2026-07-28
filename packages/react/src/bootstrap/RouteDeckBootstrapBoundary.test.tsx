// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import {
  createInitialRouteDeckState,
  type RouteDeckClientState,
  type RouteDeckStore,
} from "@routedeck/core";
import { afterEach, expect, it, vi } from "vitest";

import { RouteDeckBootstrapBoundary } from "./RouteDeckBootstrapBoundary";

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

it("renders loading, product recovery, and children from framework state", async () => {
  const harness = createStoreHarness({ syncStatus: "bootstrapping" });
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);

  await act(async () => {
    root?.render(
      <RouteDeckBootstrapBoundary
        store={harness.store}
        loading={<p>Loading buyer session</p>}
        recovery={(state) => (
          <p>
            Recover {state.phase === "recovery" ? state.reason : state.phase}
          </p>
        )}
      >
        <main>Buyer application</main>
      </RouteDeckBootstrapBoundary>,
    );
  });
  expect(container.textContent).toContain("Loading buyer session");

  await act(async () => {
    harness.setState({
      syncStatus: "error",
      pendingBootstrap: { kind: "resume_expired", status: 410 },
    });
  });
  expect(container.textContent).toContain("Recover resume_expired");
  expect(container.textContent).not.toContain("Buyer application");

  await act(async () => {
    harness.setState({
      syncStatus: "live",
      pendingBootstrap: null,
      error: null,
    });
  });
  expect(container.textContent).toContain("Buyer application");
  expect(container.textContent).not.toContain("Recover");
});

it.each(["resync_required", "resyncing", "connecting"] as const)(
  "keeps the ready application mounted during background %s synchronization",
  async (syncStatus) => {
    const harness = createStoreHarness({ syncStatus: "live" });
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(
        <RouteDeckBootstrapBoundary
          store={harness.store}
          loading={<p>Loading buyer session</p>}
          recovery={(state) => (
            <p>
              Recover {state.phase === "recovery" ? state.reason : state.phase}
            </p>
          )}
        >
          <main>Buyer application</main>
        </RouteDeckBootstrapBoundary>,
      );
    });
    expect(container.textContent).toContain("Buyer application");

    await act(async () => {
      harness.setState({ syncStatus });
    });

    expect(container.textContent).toContain("Buyer application");
    expect(container.textContent).not.toContain("Loading buyer session");
  },
);

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
  const store: RouteDeckStore = {
    getState: () => state,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    bootstrap: vi.fn(async () => undefined),
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
    resync: async () => undefined,
    synchronizeTo: async () => undefined,
    openPath: async () => undefined,
    back() {},
    forward() {},
    cancel: async () => undefined,
    retrySessionCreate: async () => undefined,
    startNewSession: async () => undefined,
    retryNavigation: async () => undefined,
    abandonNavigation: async () => undefined,
    dispose() {},
  };
  return { store, setState };
}
