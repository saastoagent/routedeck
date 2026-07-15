import { RouteDeckBootstrapCoordinator } from "./bootstrap";
import { RouteDeckEventStreamCoordinator } from "./events";
import { RouteDeckStoreLifecycle } from "./lifecycle";
import { RouteDeckNavigationCoordinator } from "./navigation";
import { RouteDeckObservableState } from "./observable";
import { RouteDeckOperationCoordinator } from "./operations";
import { RouteDeckRoutingCoordinator } from "./routing";
import { RouteDeckSynchronizationCoordinator } from "./synchronization";
import type { RouteDeckStore, RouteDeckStoreConfig } from "./types";

export type {
  RouteDeckBootstrapMode,
  RouteDeckStore,
  RouteDeckStoreConfig,
} from "./types";

export function createRouteDeckStore(config: RouteDeckStoreConfig): RouteDeckStore {
  const observable = new RouteDeckObservableState();
  let state = observable.snapshot;
  const stopMirroringState = observable.subscribe(() => {
    state = observable.snapshot;
  });
  const routing = new RouteDeckRoutingCoordinator(
    config,
    () => state.projection !== null,
  );

  let lifecycle!: RouteDeckStoreLifecycle;
  let synchronization!: RouteDeckSynchronizationCoordinator;

  const eventStream = new RouteDeckEventStreamCoordinator(
    config.client,
    observable,
    {
      isDisposed: () => lifecycle.isDisposed,
      state: () => state,
      receive: (event) => synchronization.receiveEvent(event),
      scheduleResync: () => synchronization.scheduleResync(),
    },
  );
  const navigation = new RouteDeckNavigationCoordinator(
    config,
    observable,
    routing,
    eventStream,
    {
      state: () => state,
      requireActive: () => lifecycle.requireActive(),
      reconcile: (request) => synchronization.reconcile(request),
      applySnapshot: (projection) => synchronization.applySnapshot(projection),
      resync: () => synchronization.resync("replace"),
    },
  );
  synchronization = new RouteDeckSynchronizationCoordinator(
    config,
    observable,
    routing,
    eventStream,
    navigation,
    {
      state: () => state,
      isDisposed: () => lifecycle.isDisposed,
      requireActive: () => lifecycle.requireActive(),
    },
  );
  const bootstrap = new RouteDeckBootstrapCoordinator(
    config,
    observable,
    navigation,
    {
      state: () => state,
      requireActive: () => lifecycle.requireActive(),
      resyncInFlight: () => synchronization.resyncInFlight,
      completeInitialBootstrap: (initial, context) =>
        synchronization.completeInitialBootstrap(initial, context),
      prepareNewSession: () => synchronization.prepareNewSession(),
    },
  );
  const operations = new RouteDeckOperationCoordinator(config, observable, {
    state: () => state,
    requireActive: () => lifecycle.requireActive(),
    reconcile: (request) => synchronization.reconcile(request),
    resync: () => synchronization.resync("push"),
  });

  lifecycle = new RouteDeckStoreLifecycle({
    disposeEventStream: () => eventStream.dispose(),
    disposeSynchronization: () => synchronization.dispose(),
    disposeBootstrap: () => bootstrap.dispose(),
    resetNavigation: () => navigation.reset(),
    stopMirroringState,
    disposeObservable: () => observable.dispose(),
    captureDisposedState: () => {
      state = observable.snapshot;
    },
  });

  return {
    getState() {
      return state;
    },
    subscribe(listener) {
      lifecycle.requireActive();
      return observable.subscribe(listener);
    },
    bootstrap: () => bootstrap.bootstrap(),
    dispatch: (request) => operations.dispatch(request),
    acceptReview: (reviewId, request) =>
      operations.acceptReview(reviewId, request),
    rejectReview: (reviewId, request) =>
      operations.rejectReview(reviewId, request),
    inspect: () => operations.inspect(),
    receiveEvent: (event) => synchronization.receiveEvent(event),
    resync: () => synchronization.resync("replace"),
    synchronizeTo: (target) => synchronization.synchronizeTo(target),
    openPath: (path, options = {}) =>
      navigation.openPath(path, options.replace ?? false),
    back: () => navigation.back(),
    forward: () => navigation.forward(),
    cancel: () => navigation.cancel(),
    retrySessionCreate: () => bootstrap.retrySessionCreate(),
    startNewSession: () => bootstrap.startNewSession(),
    retryNavigation: () => navigation.retry(),
    abandonNavigation: () => navigation.abandon(),
    dispose: () => lifecycle.dispose(),
  };
}
