import { RouteDeckStateError } from "@routedeck/core";
import type { RouteDeckSurfaceComponentProps } from "@routedeck/react";

const STRUCTURAL_SLOTS = new Set(["frame", "status", "error", "diagnostic"]);

export function StructuralSurface({
  surface,
  slot,
  props,
}: RouteDeckSurfaceComponentProps) {
  if (!STRUCTURAL_SLOTS.has(slot)) {
    throw new RouteDeckStateError(
      "structural_surface_slot_mismatch",
      `Structural surface ${surface.surface_id} cannot render in ${slot}.`,
    );
  }
  if (Object.keys(props).length > 0) {
    throw new RouteDeckStateError(
      "structural_surface_props_not_supported",
      `Structural surface ${surface.surface_id} projected unexpected props.`,
    );
  }
  return null;
}
