import {
  selectCurrentNode,
  selectProjection,
  selectSurfaces,
  type RouteDeckProjectedSurfaceSlots,
} from "@routedeck/core";

import { useRouteDeckRuntime } from "../provider/RouteDeckProvider";
import { useRouteDeckSelector } from "./store";

export function useRouteDeckContract() {
  return useRouteDeckRuntime().contract;
}

export function useRouteDeckProjection() {
  return useRouteDeckSelector(selectProjection);
}

export function useRouteDeckCurrentNode() {
  return useRouteDeckSelector(selectCurrentNode);
}

export function useRouteDeckSurfaces() {
  return useRouteDeckSelector(selectSurfaces);
}

export function useRouteDeckSurface(
  slot: keyof RouteDeckProjectedSurfaceSlots,
  index = 0,
) {
  return useRouteDeckSelector((state) => {
    const surfaces = state.projection?.surfaces;
    if (!surfaces) return null;
    if (slot === "active") return index === 0 ? surfaces.active : null;
    return surfaces[slot][index] ?? null;
  });
}

export function useRouteDeckDiagnostics() {
  return useRouteDeckSelector(
    (state) => state.projection?.diagnostics ?? null,
  );
}
