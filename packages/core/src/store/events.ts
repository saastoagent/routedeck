import type { RouteDeckEvent } from "../contracts/decode";
import type { RouteDeckClient } from "../client/client";
import { RouteDeckStreamError } from "../client/errors";
import type { RouteDeckEventConnection } from "../client/sse";
import { safeError } from "./errors";
import type { RouteDeckObservableState } from "./observable";
import type { RouteDeckClientState } from "./state";

export interface RouteDeckEventStreamCallbacks {
  isDisposed(): boolean;
  state(): RouteDeckClientState;
  receive(event: RouteDeckEvent): void;
  scheduleResync(): void;
}

export class RouteDeckEventStreamCoordinator {
  private connection: RouteDeckEventConnection | null = null;
  private generation = 0;

  constructor(
    private readonly client: RouteDeckClient,
    private readonly observable: RouteDeckObservableState,
    private readonly callbacks: RouteDeckEventStreamCallbacks,
  ) {}

  get connected(): boolean {
    return this.connection !== null;
  }

  invalidate(): void {
    this.generation += 1;
    this.connection?.close();
    this.connection = null;
  }

  connect(after: number): Promise<void> {
    this.invalidate();
    const generation = ++this.generation;
    let opened = false;
    let resolveOpen!: () => void;
    let rejectOpen!: (error: unknown) => void;
    const openPromise = new Promise<void>((resolve, reject) => {
      resolveOpen = resolve;
      rejectOpen = reject;
    });
    this.observable.setSyncStatus("connecting");
    this.connection = this.client.connectEvents({
      after,
      onOpen: (open) => {
        if (this.stale(generation)) return;
        const state = this.callbacks.state();
        if (open.reconnecting || state.syncStatus === "error") {
          const reconnectError = new RouteDeckStreamError(
            "stream_reconnected_snapshot_required",
            "The RouteDeck event stream reconnected and requires an authoritative snapshot.",
          );
          this.observable.requireResync(
            reconnectError.code,
            reconnectError.message,
          );
          if (!opened) rejectOpen(reconnectError);
          this.callbacks.scheduleResync();
          return;
        }
        if (state.syncStatus === "connecting") {
          this.observable.setSyncStatus("live");
        }
        opened = true;
        resolveOpen();
      },
      onEvent: (event) => {
        if (!this.stale(generation)) this.callbacks.receive(event);
      },
      onReset: () => {
        if (this.stale(generation)) return;
        this.observable.requireResync(
          "stream_reset_required",
          "The RouteDeck event cursor is outside retention.",
        );
        this.callbacks.scheduleResync();
      },
      onError: (error) => {
        if (this.stale(generation)) return;
        this.observable.setError(safeError(error));
        if (!opened) rejectOpen(error);
      },
    });
    void this.connection.done.catch((error: unknown) => {
      if (this.stale(generation)) return;
      this.observable.setError(safeError(error));
      if (!opened) rejectOpen(error);
    });
    return openPromise;
  }

  dispose(): void {
    this.invalidate();
  }

  private stale(generation: number): boolean {
    return this.callbacks.isDisposed() || generation !== this.generation;
  }
}
