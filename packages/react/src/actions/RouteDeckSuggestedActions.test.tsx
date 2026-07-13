// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import {
  type FrontendContract,
  type RouteDeckClientState,
  type RouteDeckDispatchRequest,
  type RouteDeckDispatchResult,
  type RouteDeckProjection,
  type RouteDeckStore,
} from "@routedeck/core";
import { afterEach, expect, it, vi } from "vitest";

import { RouteDeckProvider } from "../provider/RouteDeckProvider";
import { RouteDeckSuggestedActions } from "./RouteDeckSuggestedActions";

let root: Root | null = null;

afterEach(() => {
  if (root !== null) {
    act(() => root?.unmount());
    root = null;
  }
  document.body.replaceChildren();
});
it("dispatches the exact projected operation binding and arguments", async () => {
  const dispatch = vi.fn(
    async (_request: RouteDeckDispatchRequest) =>
      ({}) as RouteDeckDispatchResult,
  );
  const projection = {
    suggested_actions: [
      {
        action_id: "buyer.browse_products",
        label: "Browse products",
        operation_id: "catalog.list",
        arguments: { collection: "summer" },
      },
    ],
  } as unknown as RouteDeckProjection;
  const state = {
    projection,
    sessionVersion: 7,
    projectionVersion: 7,
    eventCursor: 0,
    syncStatus: "live",
    lastEvent: null,
    error: null,
    pendingBootstrap: null,
    pendingNavigation: null,
  } satisfies RouteDeckClientState;
  const store = {
    getState: () => state,
    subscribe: () => () => undefined,
    dispatch,
  } as unknown as RouteDeckStore;
  const host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);

  await act(async () => {
    root?.render(
      <RouteDeckProvider store={store} contract={{} as FrontendContract}>
        <RouteDeckSuggestedActions />
      </RouteDeckProvider>,
    );
  });

  const button = document.querySelector("button");
  expect(button?.textContent).toBe("Browse products");

  await act(async () => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });

  expect(dispatch).toHaveBeenCalledWith({
    operation_id: "catalog.list",
    request_id: expect.any(String),
    expected_session_version: 7,
    arguments: { collection: "summer" },
  });
});
