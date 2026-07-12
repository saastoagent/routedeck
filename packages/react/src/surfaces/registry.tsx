import type { ComponentType } from "react";
import {
  RouteDeckStateError,
  type JsonObject,
  type RouteDeckDispatchResult,
  type RouteDeckProjectedSurface,
  type SurfaceAffordanceSpec,
  type SurfaceSpec,
} from "@routedeck/core";

export type RouteDeckSurfaceSlot =
  | "frame"
  | "peer"
  | "active"
  | "detail"
  | "form"
  | "review"
  | "status"
  | "error"
  | "diagnostic";

export interface RouteDeckSurfaceComponentProps {
  surface: RouteDeckProjectedSurface;
  slot: RouteDeckSurfaceSlot;
  props: Readonly<JsonObject>;
  spec: Readonly<SurfaceSpec>;
  dispatchAffordance(
    affordanceId: string,
    argumentsValue?: JsonObject,
  ): Promise<RouteDeckDispatchResult>;
}

export type RouteDeckSurfaceComponent = ComponentType<RouteDeckSurfaceComponentProps>;
export type RouteDeckSurfaceRegistry = Readonly<
  Record<string, RouteDeckSurfaceComponent>
>;

export function defineRouteDeckSurfaceRegistry<
  const T extends Record<string, RouteDeckSurfaceComponent>,
>(registry: T): Readonly<T> {
  return Object.freeze({ ...registry });
}

export function projectedSurfaceProps(
  surface: RouteDeckProjectedSurface,
): Readonly<JsonObject> {
  const props: JsonObject = {};
  for (const entry of surface.props) {
    if (Object.hasOwn(props, entry.name)) {
      throw new RouteDeckStateError(
        "duplicate_surface_prop",
        `Surface ${surface.surface_id} projects duplicate prop ${entry.name}.`,
      );
    }
    props[entry.name] = entry.value;
  }
  return Object.freeze(props);
}

export function findSurfaceAffordance(
  spec: SurfaceSpec,
  affordanceId: string,
): SurfaceAffordanceSpec {
  const affordance = spec.affordances?.find((item) => item.id === affordanceId);
  if (!affordance) {
    throw new RouteDeckStateError(
      "surface_affordance_not_declared",
      `Surface ${spec.id} does not declare affordance ${affordanceId}.`,
    );
  }
  return affordance;
}
