import { RouteDeckStateError } from "../client/errors";
import type { RouteDeckClientState } from "./state";

export const selectProjection = (state: RouteDeckClientState) => state.projection;
export const selectSyncStatus = (state: RouteDeckClientState) => state.syncStatus;
export const selectCurrentNode = (state: RouteDeckClientState) =>
  state.projection?.current.node_id ?? null;
export const selectLegalOperations = (state: RouteDeckClientState) =>
  state.projection?.legal_operations ?? null;
export const selectSurfaces = (state: RouteDeckClientState) =>
  state.projection?.surfaces ?? null;
export const selectStatus = (state: RouteDeckClientState) =>
  state.projection?.status ?? null;

export function selectOperation(state: RouteDeckClientState, operationId: string) {
  if (!operationId) {
    throw new RouteDeckStateError(
      "operation_id_required",
      "RouteDeck operation selectors require an operation ID.",
    );
  }
  return (
    state.projection?.legal_operations.find(
      (operation) => operation.operation_id === operationId,
    ) ?? null
  );
}

export function selectCanDispatch(
  state: RouteDeckClientState,
  operationId: string,
): boolean {
  return (
    state.syncStatus === "live" && selectOperation(state, operationId) !== null
  );
}
