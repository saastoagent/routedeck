import type { RouteDeckProjection } from "../contracts/decode";
import { RouteDeckStateError } from "../client/errors";
import { createRouteDeckRouteController } from "../routing/controller";
import type { RouteDeckStoreConfig } from "./types";

export type RouteDeckHistorySyncMode = "replace" | "push" | "verify";

export class RouteDeckRoutingCoordinator {
  private readonly controller;

  constructor(
    private readonly config: RouteDeckStoreConfig,
    sessionAvailable: () => boolean,
  ) {
    this.controller =
      config.routeController ??
      (config.history && config.routes
        ? createRouteDeckRouteController({
            history: config.history,
            codec: config.routes,
            context: () => ({
              sessionAvailable: config.sessionAvailable?.() ?? sessionAvailable(),
            }),
          })
        : null);
  }

  projectionPath(projection: RouteDeckProjection): string {
    if (!this.config.routes) {
      throw new RouteDeckStateError(
        "routing_required",
        "RouteDeck URL synchronization requires compiled routes.",
      );
    }
    const params = Object.fromEntries(
      projection.current.route_params.map((parameter) => {
        if (typeof parameter.value !== "string") {
          throw new RouteDeckStateError(
            "route_parameter_invalid",
            `Route parameter ${parameter.name} must project as a string.`,
          );
        }
        return [parameter.name, parameter.value];
      }),
    );
    const resumeHandle = this.config.resumeHandleForProjection
      ? this.config.resumeHandleForProjection(projection)
      : projection.navigation.resume_handle;
    return this.config.routes.encode(projection.current.node_id, params, {
      ...(resumeHandle === null ? {} : { resumeHandle }),
    });
  }

  syncHistory(
    projection: RouteDeckProjection,
    mode: RouteDeckHistorySyncMode = "replace",
  ): void {
    if (!this.controller || !this.config.history) return;
    if (mode === "verify") {
      if (
        this.config.history.current() !== this.projectionPath(projection) ||
        this.config.history.currentEntryId() !==
          projection.navigation.current_entry_id
      ) {
        throw new RouteDeckStateError(
          "browser_history_mismatch",
          "Browser history does not match the confirmed RouteDeck location.",
        );
      }
      return;
    }
    const resumeHandle = this.config.resumeHandleForProjection
      ? this.config.resumeHandleForProjection(projection)
      : projection.navigation.resume_handle;
    this.controller.syncProjection(projection, {
      replace: mode === "replace",
      ...(resumeHandle === null ? {} : { resumeHandle }),
    });
  }
}
