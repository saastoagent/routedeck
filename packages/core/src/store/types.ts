import type {
  RouteDeckDispatchRequest,
  RouteDeckDispatchResult,
  RouteDeckEvent,
  RouteDeckInspection,
  RouteDeckProjection,
  RouteDeckReviewRequest,
} from "../contracts/decode";
import type {
  RouteDeckClient,
  RouteDeckNavigationRequest,
  RouteDeckSessionCreateRequest,
} from "../client/client";
import type { RouteDeckHistoryAdapter } from "../routing/history";
import type { RouteDeckRouteCodec } from "../routing/codec";
import type { RouteDeckRouteController } from "../routing/controller";
import type { RouteDeckClientState } from "./state";

export type RouteDeckBootstrapMode =
  | "resume"
  | "create"
  | "resume_or_create_shareable";

export interface RouteDeckStore {
  getState(): RouteDeckClientState;
  subscribe(listener: () => void): () => void;
  bootstrap(): Promise<void>;
  dispatch(request: RouteDeckDispatchRequest): Promise<RouteDeckDispatchResult>;
  acceptReview(
    reviewId: string,
    request: RouteDeckReviewRequest,
  ): Promise<RouteDeckDispatchResult>;
  rejectReview(
    reviewId: string,
    request: RouteDeckReviewRequest,
  ): Promise<RouteDeckDispatchResult>;
  inspect(): Promise<RouteDeckInspection>;
  receiveEvent(event: RouteDeckEvent): void;
  resync(): Promise<void>;
  synchronizeTo(target: {
    sessionVersion: number;
    projectionVersion: number;
  }): Promise<void>;
  openPath(path: string, options?: { replace?: boolean }): Promise<void>;
  back(): void;
  forward(): void;
  cancel(): Promise<void>;
  retrySessionCreate(): Promise<void>;
  startNewSession(): Promise<void>;
  retryNavigation(): Promise<void>;
  abandonNavigation(): Promise<void>;
  dispose(): void;
}

export interface RouteDeckStoreConfig {
  client: RouteDeckClient;
  bootstrapMode?: RouteDeckBootstrapMode;
  history?: RouteDeckHistoryAdapter;
  routes?: RouteDeckRouteCodec;
  routeController?: RouteDeckRouteController;
  sessionAvailable?: () => boolean;
  resumeHandleForProjection?: (projection: RouteDeckProjection) => string | null;
  createRequestId?: () => string;
}

export interface RetainedNavigationAttempt {
  readonly request: RouteDeckNavigationRequest;
  readonly public: NonNullable<RouteDeckClientState["pendingNavigation"]>;
  complete(projection: RouteDeckProjection): Promise<void>;
}

export interface InitialBootstrapContext {
  readonly incomingPath: string | null;
  readonly incomingEntryId: number | null;
}

export interface RetainedSessionCreateAttempt {
  readonly request: Readonly<RouteDeckSessionCreateRequest>;
  readonly public: Extract<
    NonNullable<RouteDeckClientState["pendingBootstrap"]>,
    { kind: "session_create" }
  >;
  complete(projection: RouteDeckProjection): Promise<void>;
}
