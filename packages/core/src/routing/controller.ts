import type { RouteDeckProjection } from "../contracts/decode";
import type { RouteDeckHistoryAdapter } from "./history";
import type {
  RouteDeckRouteCodec,
  RouteDeckRouteContext,
  RouteDeckRouteLocation,
} from "./codec";

export interface RouteDeckRouteController {
  current(context?: RouteDeckRouteContext): RouteDeckRouteLocation;
  navigate(
    nodeId: string,
    params: Readonly<Record<string, string>>,
    options: {
      historyEntryId: number;
      replace?: boolean;
      resumeHandle?: string;
    },
  ): RouteDeckRouteLocation;
  syncProjection(
    projection: RouteDeckProjection,
    options?: { resumeHandle?: string; replace?: boolean },
  ): RouteDeckRouteLocation;
  subscribe(
    listener: (location: RouteDeckRouteLocation) => void,
    context: () => RouteDeckRouteContext,
  ): () => void;
}

export function createRouteDeckRouteController(options: {
  codec: RouteDeckRouteCodec;
  history: RouteDeckHistoryAdapter;
  context?: () => RouteDeckRouteContext;
}): RouteDeckRouteController {
  const context = options.context ?? (() => ({ sessionAvailable: false }));

  function current(
    override?: RouteDeckRouteContext,
  ): RouteDeckRouteLocation {
    return options.codec.decode(options.history.current(), override ?? context());
  }

  return {
    current,
    navigate(nodeId, params, navigation) {
      const path = options.codec.encode(nodeId, params, {
        ...(navigation.resumeHandle === undefined
          ? {}
          : { resumeHandle: navigation.resumeHandle }),
      });
      if (navigation.replace) {
        options.history.replace(path, navigation.historyEntryId);
      } else {
        options.history.push(path, navigation.historyEntryId);
      }
      return options.codec.decode(path, context());
    },
    syncProjection(projection, synchronization = {}) {
      const params = Object.fromEntries(
        projection.current.route_params.map((value) => {
          if (typeof value.value !== "string") {
            throw new TypeError(
              `Route parameter ${value.name} must project as a string.`,
            );
          }
          return [value.name, value.value];
        }),
      );
      const path = options.codec.encode(projection.current.node_id, params, {
        ...(synchronization.resumeHandle === undefined
          ? {}
          : { resumeHandle: synchronization.resumeHandle }),
      });
      if (synchronization.replace ?? true) {
        options.history.replace(path, projection.navigation.current_entry_id);
      } else {
        options.history.push(path, projection.navigation.current_entry_id);
      }
      return options.codec.decode(path, context());
    },
    subscribe(listener, routeContext) {
      return options.history.subscribe((path) => {
        listener(options.codec.decode(path, routeContext()));
      });
    },
  };
}
