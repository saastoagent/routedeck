import type {
  RouteDeckBootstrapRecoveryActionKind,
  RouteDeckBootstrapRecoveryReason,
  RouteDeckClientErrorState,
  RouteDeckSyncStatus,
} from "@routedeck/core";

export type {
  RouteDeckBootstrapRecoveryActionKind,
  RouteDeckBootstrapRecoveryReason,
} from "@routedeck/core";

export interface RouteDeckBootstrapRecoveryAction {
  readonly kind: RouteDeckBootstrapRecoveryActionKind;
  run(): Promise<void>;
}

export interface RouteDeckBootstrapLoadingState {
  readonly phase: "loading";
  readonly syncStatus: RouteDeckSyncStatus;
  readonly busy: true;
}

export interface RouteDeckBootstrapReadyState {
  readonly phase: "ready";
  readonly syncStatus: "live";
  readonly busy: false;
}

export interface RouteDeckBootstrapActionRequiredState {
  readonly phase: "recovery";
  readonly syncStatus: RouteDeckSyncStatus;
  readonly reason: RouteDeckBootstrapRecoveryReason;
  readonly busy: boolean;
  readonly activeAction: RouteDeckBootstrapRecoveryActionKind | null;
  readonly error: RouteDeckClientErrorState | null;
  readonly actions: readonly RouteDeckBootstrapRecoveryAction[];
}

export interface RouteDeckBootstrapDisposedState {
  readonly phase: "disposed";
  readonly syncStatus: "disposed";
  readonly busy: false;
  readonly error: RouteDeckClientErrorState | null;
  readonly actions: readonly [];
}

export type RouteDeckBootstrapRecoveryState =
  | RouteDeckBootstrapLoadingState
  | RouteDeckBootstrapReadyState
  | RouteDeckBootstrapActionRequiredState
  | RouteDeckBootstrapDisposedState;
