import type { ComponentType } from "react";
import {
  RouteDeckStateError,
  type FrontendContract,
  type FrontendSurfaceContract,
  type JsonObject,
  type RouteDeckDispatchResult,
  type RouteDeckProjectedSurface,
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
  spec: Readonly<FrontendSurfaceContract>;
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

export function validateRouteDeckSurfaceRegistry(
  contract: FrontendContract,
  registry: RouteDeckSurfaceRegistry,
): void {
  const declaredComponents = new Set(
    Object.values(contract.surfaces).map((surface) => surface.component),
  );
  const registeredComponents = new Set(Object.keys(registry));
  const missing = [...declaredComponents]
    .filter((component) => !registeredComponents.has(component))
    .sort();
  const extra = [...registeredComponents]
    .filter((component) => !declaredComponents.has(component))
    .sort();

  if (missing.length === 0 && extra.length === 0) {
    return;
  }

  const details = [
    missing.length > 0 ? `Missing: ${missing.join(", ")}.` : undefined,
    extra.length > 0 ? `Extra: ${extra.join(", ")}.` : undefined,
  ]
    .filter((detail): detail is string => detail !== undefined)
    .join(" ");

  throw new RouteDeckStateError(
    "surface_registry_mismatch",
    `Surface registry does not match the compiled contract. ${details}`,
  );
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
  spec: FrontendSurfaceContract,
  affordanceId: string,
): NonNullable<FrontendSurfaceContract["affordances"]>[number] {
  const affordance = spec.affordances?.find((item) => item.id === affordanceId);
  if (!affordance) {
    throw new RouteDeckStateError(
      "surface_affordance_not_declared",
      `Surface ${spec.id} does not declare affordance ${affordanceId}.`,
    );
  }
  return affordance;
}
