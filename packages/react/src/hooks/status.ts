import { useCallback } from "react";
import { selectStatus, selectSyncStatus } from "@routedeck/core";

import { useRouteDeckRuntime } from "../provider/RouteDeckProvider";
import { useRouteDeckSelector } from "./store";

export function useRouteDeckStatus() {
  return useRouteDeckSelector(selectStatus);
}

export function useRouteDeckSyncStatus() {
  return useRouteDeckSelector(selectSyncStatus);
}

export function useRouteDeckClientError() {
  return useRouteDeckSelector((state) => state.error);
}

export function useRouteDeckInspect() {
  const { store } = useRouteDeckRuntime();
  return useCallback(async () => {
    return store.inspect();
  }, [store]);
}
