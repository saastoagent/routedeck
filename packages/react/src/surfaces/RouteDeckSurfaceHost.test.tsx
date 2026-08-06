// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import type {
  FrontendContract,
  RouteDeckClientState,
  RouteDeckProjection,
  RouteDeckStore,
} from "@routedeck/core";
import { afterEach, expect, it } from "vitest";

import { RouteDeckProvider } from "../provider/RouteDeckProvider";
import { defineRouteDeckSurfaceRegistry } from "./registry";
import { RouteDeckSurfaceHost } from "./RouteDeckSurfaceHost";

let root: Root | null = null;
(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

afterEach(() => {
  if (root !== null) {
    act(() => root?.unmount());
    root = null;
  }
  document.body.replaceChildren();
});

it("keeps projected surfaces inert while the store is resynchronizing", async () => {
  const projection = {
    interaction: { phase: "idle", owner: null },
    projection_version: 4,
    surfaces: {
      frame: [],
      peer: [],
      active: {
        surface_id: "test.surface",
        component: "test.surface",
        props: [],
      },
      detail: [],
      form: [],
      review: [],
      status: [],
      error: [],
      diagnostic: [],
    },
  } as unknown as RouteDeckProjection;
  const state = {
    projection,
    sessionVersion: 4,
    projectionVersion: 4,
    eventCursor: 0,
    syncStatus: "resyncing",
    lastEvent: null,
    error: null,
    pendingBootstrap: null,
    pendingNavigation: null,
  } satisfies RouteDeckClientState;
  const store = {
    getState: () => state,
    subscribe: () => () => undefined,
  } as unknown as RouteDeckStore;
  const contract = {
    name: "surface-sync-test",
    entry_node_id: "test.home",
    nodes: {},
    transitions: [],
    surfaces: {
      "test.surface": {
        id: "test.surface",
        component: "test.surface",
        lifecycle: "stable",
        affordances: [],
        public_props_schema: {},
      },
    },
  } as FrontendContract;
  const registry = defineRouteDeckSurfaceRegistry({
    "test.surface": () => <button type="button">Back to Lounge</button>,
  });
  const host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);

  await act(async () => {
    root?.render(
      <RouteDeckProvider store={store} contract={contract}>
        <RouteDeckSurfaceHost registry={registry} />
      </RouteDeckProvider>,
    );
  });

  const surface = document.querySelector("[data-routedeck-surface='test.surface']");
  expect(surface?.getAttribute("aria-busy")).toBe("true");
  expect(surface?.hasAttribute("inert")).toBe(true);
});
