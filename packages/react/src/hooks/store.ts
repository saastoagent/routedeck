import { useCallback, useRef, useSyncExternalStore } from "react";
import type { RouteDeckClientState, RouteDeckStore } from "@routedeck/core";

import { useRouteDeckRuntime } from "../provider/RouteDeckProvider";

export function useRouteDeckStore(): RouteDeckStore {
  return useRouteDeckRuntime().store;
}

export function useRouteDeckSelector<T>(
  selector: (state: RouteDeckClientState) => T,
  isEqual: (left: T, right: T) => boolean = Object.is,
): T {
  const store = useRouteDeckStore();
  const cache = useRef<{ state: RouteDeckClientState; value: T } | null>(null);
  const getSnapshot = useCallback(() => {
    const state = store.getState();
    const previous = cache.current;
    if (previous?.state === state) return previous.value;
    const next = selector(state);
    if (previous !== null && isEqual(previous.value, next)) {
      cache.current = { state, value: previous.value };
      return previous.value;
    }
    cache.current = { state, value: next };
    return next;
  }, [store, selector, isEqual]);

  return useSyncExternalStore(store.subscribe, getSnapshot, getSnapshot);
}
