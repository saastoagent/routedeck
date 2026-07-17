import type { RouteDeckProjection } from "../contracts/decode";
import {
  createRouteDeckRequestId,
  type RouteDeckSessionCreateRequest,
} from "../client/client";
import {
  RouteDeckOutcomeUnknownError,
  RouteDeckStateError,
} from "../client/errors";
import { retainRouteDeckRequest } from "../client/retained";
import {
  isExpiredBootstrapError,
  isMissingBootstrapError,
  isUpgradeBootstrapError,
  safeError,
} from "./errors";
import type { RouteDeckNavigationCoordinator } from "./navigation";
import type { RouteDeckObservableState } from "./observable";
import type { RouteDeckClientState } from "./state";
import type {
  InitialBootstrapContext,
  RetainedSessionCreateAttempt,
  RouteDeckStoreConfig,
} from "./types";

export interface RouteDeckBootstrapHost {
  state(): RouteDeckClientState;
  requireActive(): void;
  resyncInFlight(): boolean;
  completeInitialBootstrap(
    initial: RouteDeckProjection,
    context: InitialBootstrapContext,
  ): Promise<void>;
  prepareNewSession(): void;
}

export class RouteDeckBootstrapCoordinator {
  private bootstrapInFlight = false;
  private retainedSessionCreate: RetainedSessionCreateAttempt | null = null;

  constructor(
    private readonly config: RouteDeckStoreConfig,
    private readonly observable: RouteDeckObservableState,
    private readonly navigation: RouteDeckNavigationCoordinator,
    private readonly host: RouteDeckBootstrapHost,
  ) {}

  async bootstrap(): Promise<void> {
    this.host.requireActive();
    const state = this.host.state();
    if (state.pendingBootstrap !== null || this.navigation.hasRetainedAttempt) {
      throw new RouteDeckStateError(
        "bootstrap_recovery_required",
        "Resolve the retained RouteDeck bootstrap request explicitly before bootstrapping again.",
      );
    }
    this.requireRecoveryAvailable();
    this.bootstrapInFlight = true;
    this.observable.startBootstrap();
    try {
      const context: InitialBootstrapContext = Object.freeze({
        incomingPath: this.config.history?.current() ?? null,
        incomingEntryId: this.config.history?.currentEntryId() ?? null,
      });
      const initial = await this.bootstrapProjection((projection) =>
        this.host.completeInitialBootstrap(projection, context),
      );
      if (initial !== null) {
        await this.host.completeInitialBootstrap(initial, context);
      }
    } catch (error) {
      if (isExpiredBootstrapError(error)) {
        this.observable.setBootstrapFailure(safeError(error), {
          kind: "resume_expired",
          status: 410,
        });
      } else if (isMissingBootstrapError(error)) {
        this.observable.setBootstrapFailure(safeError(error), {
          kind: "resume_missing",
          status: 404,
        });
      } else if (isUpgradeBootstrapError(error)) {
        this.observable.setBootstrapFailure(safeError(error), {
          kind: "resume_contract_mismatch",
          status: 409,
        });
      } else {
        this.observable.setError(safeError(error));
      }
      throw error;
    } finally {
      this.bootstrapInFlight = false;
    }
  }

  async retrySessionCreate(): Promise<void> {
    this.host.requireActive();
    this.requireRecoveryAvailable();
    if (this.retainedSessionCreate === null) {
      throw new RouteDeckStateError(
        "session_create_retry_missing",
        "There is no outcome-unknown session-create request to retry.",
      );
    }
    await this.executeSessionCreateAttempt(this.retainedSessionCreate);
  }

  async startNewSession(): Promise<void> {
    this.host.requireActive();
    this.requireRecoveryAvailable();
    this.requireNewSessionRecovery();
    this.host.prepareNewSession();
    this.retainedSessionCreate = null;
    this.navigation.reset();
    this.observable.resetForBootstrap();
    const freshContext: InitialBootstrapContext = Object.freeze({
      incomingPath: null,
      incomingEntryId: null,
    });
    await this.executeSessionCreateAttempt(
      this.createSessionAttempt((projection) =>
        this.host.completeInitialBootstrap(projection, freshContext),
      ),
    );
  }

  dispose(): void {
    this.retainedSessionCreate = null;
  }

  private requireRecoveryAvailable(): void {
    if (
      this.bootstrapInFlight ||
      this.navigation.inFlight ||
      this.host.resyncInFlight()
    ) {
      throw new RouteDeckStateError(
        "bootstrap_in_progress",
        "RouteDeck bootstrap recovery is already in progress.",
      );
    }
  }

  private requireNewSessionRecovery(): void {
    const pending = this.host.state().pendingBootstrap;
    if (
      pending?.kind !== "session_create" &&
      pending?.kind !== "resume_expired" &&
      pending?.kind !== "resume_missing" &&
      pending?.kind !== "resume_contract_mismatch"
    ) {
      throw new RouteDeckStateError(
        "new_session_recovery_unavailable",
        "A new session is only available for uncertain, expired, or missing bootstrap recovery.",
      );
    }
  }

  private async bootstrapProjection(
    complete: RetainedSessionCreateAttempt["complete"],
  ): Promise<RouteDeckProjection | null> {
    const mode = this.config.bootstrapMode ?? "resume";
    if (mode === "create") {
      await this.executeSessionCreateAttempt(this.createSessionAttempt(complete));
      return null;
    }
    try {
      return await this.config.client.getSession();
    } catch (error) {
      if (
        mode !== "resume_or_create_shareable" ||
        (!isMissingBootstrapError(error) &&
          !isExpiredBootstrapError(error) &&
          !isUpgradeBootstrapError(error))
      ) {
        throw error;
      }
      if (!this.config.routes || !this.config.history) {
        throw new RouteDeckStateError(
          "shareable_bootstrap_requires_routing",
          "Shareable session creation requires the compiled route codec and history adapter.",
        );
      }
      if (
        this.config.routes.policyForPath(this.config.history.current()) !==
        "shareable"
      ) {
        throw error;
      }
      await this.executeSessionCreateAttempt(this.createSessionAttempt(complete));
      return null;
    }
  }

  private createSessionAttempt(
    complete: RetainedSessionCreateAttempt["complete"],
  ): RetainedSessionCreateAttempt {
    const retained = retainRouteDeckRequest<RouteDeckSessionCreateRequest>({
      request_id: (this.config.createRequestId ?? createRouteDeckRequestId)(),
    });
    return Object.freeze({
      request: retained.request,
      public: Object.freeze({
        kind: "session_create" as const,
      }),
      complete,
    });
  }

  private async executeSessionCreateAttempt(
    attempt: RetainedSessionCreateAttempt,
  ): Promise<void> {
    this.bootstrapInFlight = true;
    this.observable.startBootstrap(attempt.public);
    try {
      let projection: RouteDeckProjection;
      try {
        projection = await this.config.client.createSession(attempt.request);
      } catch (error) {
        if (error instanceof RouteDeckOutcomeUnknownError) {
          if (error.requestId !== attempt.request.request_id) {
            this.retainedSessionCreate = null;
            const mismatch = new RouteDeckStateError(
              "session_create_request_identity_mismatch",
              "The outcome-unknown failure does not match the retained session-create request.",
            );
            this.observable.setBootstrapFailure(safeError(mismatch), null);
            throw mismatch;
          }
          this.retainedSessionCreate = attempt;
          this.observable.setBootstrapFailure(safeError(error), attempt.public);
        } else {
          if (this.retainedSessionCreate === attempt) {
            this.retainedSessionCreate = null;
          }
          this.observable.setBootstrapFailure(safeError(error), null);
        }
        throw error;
      }

      if (this.retainedSessionCreate === attempt) {
        this.retainedSessionCreate = null;
      }
      this.observable.setPendingBootstrap(null);
      await attempt.complete(projection);
    } finally {
      this.bootstrapInFlight = false;
    }
  }
}
