import { RouteDeckStateError } from "../client/errors";

export interface RouteDeckStoreCleanup {
  disposeEventStream(): void;
  disposeSynchronization(): void;
  disposeBootstrap(): void;
  resetNavigation(): void;
  stopMirroringState(): void;
  disposeObservable(): void;
  captureDisposedState(): void;
}

export class RouteDeckStoreLifecycle {
  private disposed = false;

  constructor(private readonly cleanup: RouteDeckStoreCleanup) {}

  get isDisposed(): boolean {
    return this.disposed;
  }

  requireActive(): void {
    if (this.disposed) {
      throw new RouteDeckStateError(
        "store_disposed",
        "The RouteDeck store has been disposed.",
      );
    }
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.cleanup.disposeEventStream();
    this.cleanup.disposeSynchronization();
    this.cleanup.disposeBootstrap();
    this.cleanup.resetNavigation();
    this.cleanup.stopMirroringState();
    this.cleanup.disposeObservable();
    this.cleanup.captureDisposedState();
  }
}
