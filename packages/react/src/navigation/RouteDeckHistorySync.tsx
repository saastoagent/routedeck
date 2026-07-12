import { useEffect, useRef } from "react";
import { RouteDeckStateError } from "@routedeck/core";

import { useRouteDeckRuntime } from "../provider/RouteDeckProvider";

export function RouteDeckHistorySync() {
  const { routeController, navigationActions, store } = useRouteDeckRuntime();
  const openRef = useRef(navigationActions?.open);
  openRef.current = navigationActions?.open;

  useEffect(() => {
    if (routeController === null) {
      throw new RouteDeckStateError(
        "route_controller_required",
        "RouteDeckHistorySync requires a route controller.",
      );
    }
    if (!openRef.current) {
      throw new RouteDeckStateError(
        "history_open_action_required",
        "RouteDeckHistorySync requires an explicit history-open action.",
      );
    }
    return routeController.subscribe(
      (location) => void openRef.current?.(location),
      () => ({ sessionAvailable: store.getState().projection !== null }),
    );
  }, [routeController, store]);

  return null;
}
