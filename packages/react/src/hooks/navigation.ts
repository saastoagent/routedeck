import { useRouteDeckRuntime } from "../provider/RouteDeckProvider";
import { useRouteDeckSelector } from "./store";

export function useRouteDeckNavigation() {
  return useRouteDeckSelector(
    (state) => state.projection?.navigation ?? null,
  );
}

export function useRouteDeckNavigationActions() {
  return useRouteDeckRuntime().navigationActions;
}

export function useRouteDeckNavigationRecovery() {
  const pending = useRouteDeckSelector((state) => state.pendingNavigation);
  const actions = useRouteDeckRuntime().navigationActions;
  return {
    pending,
    retry: actions?.retryNavigation ?? null,
    abandon: actions?.abandonNavigation ?? null,
  };
}
