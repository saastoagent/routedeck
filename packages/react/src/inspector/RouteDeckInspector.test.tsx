// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import type {
  FrontendContract,
  RouteDeckClientState,
  RouteDeckInspection,
  RouteDeckStore,
} from "@routedeck/core";
import { afterEach, expect, it, vi } from "vitest";

import { RouteDeckProvider } from "../provider/RouteDeckProvider";
import { RouteDeckInspector } from "./RouteDeckInspector";

let root: Root | null = null;

afterEach(() => {
  act(() => root?.unmount());
  root = null;
  document.body.replaceChildren();
});

it("owns and renders the complete current-snapshot context inspection", async () => {
  const inspection = {
    current_node: "test.home",
    reachable_nodes: ["test.next"],
    legal_operations: [],
    blocked_operations: [{ operation_id: "test.blocked" }],
    guard_explanations: ["test.guard"],
    capabilities: [],
    surfaces: {},
    route_traces: [],
    diagnostics: { session_version: 3 },
    agent_context: {
      kind: "current_snapshot",
      snapshot: { session_version: 3, projection_version: 2, event_cursor: 8 },
      model: { provider: "ollama", name: "test-model" },
      model_context: {
        current_node: "test.home",
        active_surface: null,
        visible_entities: [],
        legal_tools: [],
        suggested_actions: [],
        policies: [],
        status: { code: "ready" },
        recent_observations: [],
      },
      policy_resolution: [{
        policy_id: "test.policy",
        instruction: "Stay scoped.",
        scope: "node",
        owner_id: "test.home",
        source_order: 0,
      }],
      prompt: {
        base: "Base prompt",
        policy_section: "Policy section",
        context_section: "Context section",
        assembled: "Exact assembled prompt",
      },
      system_prompt: "Exact assembled prompt",
      messages: [{ id: "user-1", role: "human", content: "Hello" }],
      tools: [],
      limits: { recent_observations: 8 },
      intentional_exclusions: ["private_form_values"],
    },
  } satisfies RouteDeckInspection;
  const inspect = vi.fn(async () => inspection);
  const state = {
    projection: null,
    sessionVersion: 3,
    projectionVersion: 2,
    eventCursor: 8,
    syncStatus: "live",
    lastEvent: null,
    error: null,
    pendingBootstrap: null,
    pendingNavigation: null,
  } satisfies RouteDeckClientState;
  const store = {
    getState: () => state,
    subscribe: () => () => undefined,
    inspect,
  } as unknown as RouteDeckStore;
  const host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);

  await act(async () => {
    root?.render(
      <RouteDeckProvider store={store} contract={{} as FrontendContract}>
        <RouteDeckInspector
          initialView="context"
          className="product-inspector"
          style={{ color: "rgb(1, 2, 3)" }}
        />
      </RouteDeckProvider>,
    );
  });

  expect(inspect).toHaveBeenCalledOnce();
  expect(document.querySelector("[data-routedeck-inspector]")?.className).toBe(
    "product-inspector",
  );
  expect(document.querySelector<HTMLElement>("[data-routedeck-inspector]")?.style.color).toBe(
    "rgb(1, 2, 3)",
  );
  expect(document.body.textContent).toContain("Current agent context");
  expect(document.body.textContent).toContain("test.policy");
  expect(document.body.textContent).toContain("node · test.home");
  expect(document.body.textContent).toContain("Exact assembled prompt");
  expect(document.body.textContent).toContain("Navgraph diagnostics");
});
