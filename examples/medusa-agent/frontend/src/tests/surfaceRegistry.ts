import type { FrontendContract } from "@routedeck/core";
import {
  defineRouteDeckSurfaceRegistry,
  type RouteDeckSurfaceRegistry,
} from "@routedeck/react";

import { medusaRouteDeckSurfaces } from "../routedeck/surfaces";


export function testSurfaceRegistryForContract(
  contract: FrontendContract,
): RouteDeckSurfaceRegistry {
  const components = new Set(
    Object.values(contract.surfaces).map((surface) => surface.component),
  );
  return defineRouteDeckSurfaceRegistry(
    Object.fromEntries(
      Object.entries(medusaRouteDeckSurfaces).filter(([component]) =>
        components.has(component),
      ),
    ),
  );
}
