import { useCallback, type ReactNode } from "react";
import { RouteDeckStateError, type RouteDeckProjectedSurface } from "@routedeck/core";

import { useRouteDeckContract, useRouteDeckProjection } from "../hooks/projection";
import { useRouteDeckSyncStatus } from "../hooks/status";
import {
  useRouteDeckDispatch,
  useRouteDeckMutationRecovery,
} from "../hooks/operations";
import { RouteDeckError } from "../status/RouteDeckError";
import {
  findSurfaceAffordance,
  projectedSurfaceProps,
  validateRouteDeckSurfaceRegistry,
  type RouteDeckSurfaceRegistry,
  type RouteDeckSurfaceSlot,
} from "./registry";

const SLOT_ORDER: readonly RouteDeckSurfaceSlot[] = Object.freeze([
  "frame",
  "peer",
  "active",
  "detail",
  "form",
  "review",
  "status",
  "error",
  "diagnostic",
]);

export interface RouteDeckSurfaceHostProps {
  registry: RouteDeckSurfaceRegistry;
  slots?: readonly RouteDeckSurfaceSlot[];
  className?: string;
  empty?: ReactNode;
}

export function RouteDeckSurfaceHost({
  registry,
  slots = SLOT_ORDER,
  className,
  empty = null,
}: RouteDeckSurfaceHostProps) {
  const contract = useRouteDeckContract();
  const projection = useRouteDeckProjection();
  const syncStatus = useRouteDeckSyncStatus();
  try {
    validateRouteDeckSurfaceRegistry(contract, registry);
  } catch (error) {
    if (error instanceof RouteDeckStateError) {
      return <RouteDeckError code={error.code} message={error.message} />;
    }
    throw error;
  }
  if (projection === null) return <>{empty}</>;
  const entries = slots.flatMap((slot) => {
    const projected = projection.surfaces[slot];
    const surfaces = Array.isArray(projected)
      ? projected
      : projected === null
        ? []
        : [projected];
    return surfaces.map((surface, index) => ({ index, slot, surface }));
  });
  if (entries.length === 0) return <>{empty}</>;
  const interactionBusy = projection.interaction.phase === "active";
  const synchronizationBusy = syncStatus !== "live";

  return (
    <div className={className} data-routedeck-surface-host="">
      {entries.map(({ index, slot, surface }) => (
        <SurfaceRenderer
          key={`${slot}:${surface.surface_id}:${index}`}
          surface={surface}
          slot={slot}
          registry={registry}
          projectionVersion={projection.projection_version}
          interactionBusy={interactionBusy}
          synchronizationBusy={synchronizationBusy}
        />
      ))}
    </div>
  );
}

function SurfaceRenderer({
  surface,
  slot,
  registry,
  projectionVersion,
  interactionBusy,
  synchronizationBusy,
}: {
  surface: RouteDeckProjectedSurface;
  slot: RouteDeckSurfaceSlot;
  registry: RouteDeckSurfaceRegistry;
  projectionVersion: number;
  interactionBusy: boolean;
  synchronizationBusy: boolean;
}) {
  const contract = useRouteDeckContract();
  const dispatch = useRouteDeckDispatch();
  const mutation = useRouteDeckMutationRecovery();
  const spec = contract.surfaces[surface.surface_id];
  const Component = registry[surface.component];

  const dispatchAffordance = useCallback(
    async (affordanceId: string, argumentsValue = {}) => {
      if (synchronizationBusy) {
        throw new RouteDeckStateError(
          "store_not_ready",
          "RouteDeck is synchronizing the active surface.",
        );
      }
      if (interactionBusy) {
        throw new RouteDeckStateError(
          "interaction_in_progress",
          "RouteDeck is completing another interaction.",
        );
      }
      if (!spec) {
        throw new RouteDeckStateError(
          "surface_contract_mismatch",
          `Surface ${surface.surface_id} is absent from the compiled contract.`,
        );
      }
      const affordance = findSurfaceAffordance(spec, affordanceId);
      const operationId = affordance.operation?.id;
      if (!operationId) {
        throw new RouteDeckStateError(
          "surface_affordance_has_no_operation",
          `Surface affordance ${affordanceId} is not bound to an operation.`,
        );
      }
      return dispatch(operationId, argumentsValue);
    },
    [dispatch, interactionBusy, spec, surface.surface_id, synchronizationBusy],
  );

  if (!spec || spec.component !== surface.component) {
    return (
      <RouteDeckError
        code="surface_contract_mismatch"
        message={`Surface ${surface.surface_id} does not match the compiled frontend contract.`}
      />
    );
  }
  if (!Component) {
    return (
      <RouteDeckError
        code="surface_not_registered"
        message={`Surface component is not registered: ${surface.component}.`}
      />
    );
  }

  const lifecycleKey =
    spec.lifecycle === "ephemeral"
      ? `${surface.surface_id}:${projectionVersion}`
      : surface.surface_id;

  return (
    <section
      key={lifecycleKey}
      aria-busy={mutation.inFlight || interactionBusy || synchronizationBusy}
      inert={mutation.inFlight || interactionBusy || synchronizationBusy}
      data-routedeck-slot={slot}
      data-routedeck-surface={surface.surface_id}
    >
      <Component
        surface={surface}
        slot={slot}
        props={projectedSurfaceProps(surface)}
        spec={spec}
        dispatchAffordance={dispatchAffordance}
      />
    </section>
  );
}
