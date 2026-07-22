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
  const store = {
    getState: () => state,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    bootstrap: vi.fn(async () => undefined),
  } as unknown as RouteDeckStore;
  return { store, setState };
}
