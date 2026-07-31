import type { FrontendContract } from "@routedeck/core";
import { describe, expect, it } from "vitest";

import { buildNavGraphTopology, type NavGraphInspectorEdge } from "./topology";

describe("buildNavGraphTopology", () => {
  it("lays out broad graphs as compact wrapped sitemap layers", () => {
    const nodeIds = Array.from({ length: 10 }, (_, index) => `node.${index}`);
    const contract = {
      entry_node_id: nodeIds[0],
      nodes: Object.fromEntries(
        nodeIds.map((id, index) => [
          id,
          {
            id,
            title: `Node ${index}`,
            route_template: index === 0 ? "/" : `/route-${index}`,
            deep_link_policy: "shareable",
            conversation_input: { enabled: true, disabled_message: null },
            operation_ids: [],
            surfaces: { active: null },
          },
        ]),
      ),
      surfaces: {},
      transitions: [],
    } as unknown as FrontendContract;
    const edges: NavGraphInspectorEdge[] = [
      ...nodeIds.slice(1, 8).map((target, index) => ({
        id: `root-${index}`,
        from: nodeIds[0]!,
        to: target,
      })),
      { id: "left-leaf", from: nodeIds[1]!, to: nodeIds[8]! },
      { id: "right-leaf", from: nodeIds[2]!, to: nodeIds[9]! },
    ];

    const topology = buildNavGraphTopology(contract, edges);
    const firstLayer = topology.nodes.filter((node) => node.depth === 1);
    const secondLayer = topology.nodes.filter((node) => node.depth === 2);

    expect(topology.structuralConnections).toHaveLength(9);
    expect(new Set(firstLayer.map((node) => node.y)).size).toBe(2);
    expect(
      Math.min(...secondLayer.map((node) => node.y)),
    ).toBeGreaterThan(Math.max(...firstLayer.map((node) => node.y)));
    expect(topology.height).toBeLessThan(700);
  });

  it("keeps disconnected nodes together in one final layer", () => {
    const contract = {
      entry_node_id: "root",
      nodes: Object.fromEntries(
        ["root", "child", "detached-a", "detached-b"].map((id) => [
          id,
          {
            id,
            title: id,
            route_template: id === "root" ? "/" : `/${id}`,
            deep_link_policy: "shareable",
            conversation_input: { enabled: true, disabled_message: null },
            operation_ids: [],
            surfaces: { active: null },
          },
        ]),
      ),
      surfaces: {},
      transitions: [],
    } as unknown as FrontendContract;

    const topology = buildNavGraphTopology(contract, [
      { id: "root-child", from: "root", to: "child" },
    ]);
    const detached = topology.nodes.filter((node) => node.id.startsWith("detached"));

    expect(detached.map((node) => node.depth)).toEqual([2, 2]);
    expect(new Set(detached.map((node) => node.y)).size).toBe(1);
  });
});
