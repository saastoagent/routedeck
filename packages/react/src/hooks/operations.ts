import { useCallback, useSyncExternalStore } from "react";
import {
  selectLegalOperations,
  selectOperation,
} from "@routedeck/core";

import { useRouteDeckRuntime } from "../provider/RouteDeckProvider";
import { useRouteDeckSelector } from "./store";

export function useRouteDeckOperations() {
  return useRouteDeckSelector(selectLegalOperations);
}

export function useRouteDeckOperation(operationId: string) {
  return useRouteDeckSelector((state) => selectOperation(state, operationId));
}

export function useRouteDeckDispatch() {
  return useRouteDeckRuntime().mutationController.dispatch;
}

export function useRouteDeckReviewActions() {
  const { mutationController } = useRouteDeckRuntime();
  return {
    accept: useCallback(
      (reviewId: string) => mutationController.acceptReview(reviewId),
      [mutationController],
    ),
    reject: useCallback(
      (reviewId: string) => mutationController.rejectReview(reviewId),
      [mutationController],
    ),
  };
}

export function useRouteDeckMutationRecovery() {
  const { mutationController } = useRouteDeckRuntime();
  const state = useSyncExternalStore(
    mutationController.subscribe,
    mutationController.getState,
    mutationController.getState,
  );
  return {
    ...state,
    retry: mutationController.retry,
    abandon: mutationController.abandon,
  };
}
