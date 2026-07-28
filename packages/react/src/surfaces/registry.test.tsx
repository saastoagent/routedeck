import type { FrontendContract } from "@routedeck/core";
import { describe, expect, it } from "vitest";

import {
  defineRouteDeckSurfaceRegistry,
  validateRouteDeckSurfaceRegistry,
} from "./registry";

const Surface = () => null;

describe("validateRouteDeckSurfaceRegistry", () => {
  it("accepts the exact unique component set declared by the contract", () => {
    const contract = contractWithComponents("workspace.auth", "workspace.auth");
    const registry = defineRouteDeckSurfaceRegistry({
      "workspace.auth": Surface,
    });

    expect(() => validateRouteDeckSurfaceRegistry(contract, registry)).not.toThrow();
  });

  it("fails with exact missing and extra component names", () => {
    const contract = contractWithComponents("workspace.auth", "workspace.home");
    const registry = defineRouteDeckSurfaceRegistry({
      "workspace.auth": Surface,
      "workspace.legacy": Surface,
    });

    expect(() => validateRouteDeckSurfaceRegistry(contract, registry)).toThrowError(
      "Surface registry does not match the compiled contract. Missing: workspace.home. Extra: workspace.legacy.",
    );
  });
});

function contractWithComponents(...components: string[]): FrontendContract {
  return {
    name: "surface-registry-test",
    entry_node_id: "test.home",
    nodes: {},
    transitions: [],
    surfaces: Object.fromEntries(
      components.map((component, index) => [
        `surface.${index}`,
        {
          id: `surface.${index}`,
          component,
          lifecycle: "stable" as const,
          affordances: [],
          public_props_schema: {},
        },
      ]),
    ),
  };
}
