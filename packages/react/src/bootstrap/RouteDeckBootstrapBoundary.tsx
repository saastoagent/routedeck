import type { ReactNode } from "react";
import type { RouteDeckStore } from "@routedeck/core";

import type {
  RouteDeckBootstrapActionRequiredState,
  RouteDeckBootstrapDisposedState,
} from "./types";
import { useRouteDeckBootstrapRecovery } from "./useRouteDeckBootstrapRecovery";

export interface RouteDeckBootstrapBoundaryProps {
  readonly store: RouteDeckStore;
  readonly loading: ReactNode;
  readonly recovery: (
    state:
      | RouteDeckBootstrapActionRequiredState
      | RouteDeckBootstrapDisposedState,
  ) => ReactNode;
  readonly children: ReactNode;
}

export function RouteDeckBootstrapBoundary({
  store,
  loading,
  recovery,
  children,
}: RouteDeckBootstrapBoundaryProps) {
  const state = useRouteDeckBootstrapRecovery(store);
  if (state.phase === "loading") return loading;
  if (state.phase === "ready") return children;
  return recovery(state);
}
