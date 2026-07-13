import type {
  JsonObject,
  FrontendContract,
  RouteDeckClient,
  RouteDeckDispatchRequest,
  RouteDeckDispatchResult,
  RouteDeckEvent,
  RouteDeckEventConnection,
  RouteDeckEventStreamOptions,
  RouteDeckHistoryAdapter,
  RouteDeckInspection,
  RouteDeckNavigationRequest,
  RouteDeckPrivateFormSaved,
  RouteDeckPrivateFormSnapshot,
  RouteDeckProjection,
  RouteDeckReviewRequest,
  RouteDeckSessionCreateRequest,
} from "@routedeck/core";

export class ScriptedRouteDeckClient implements RouteDeckClient {
  readonly calls: string[] = [];
  readonly navigationRequests: RouteDeckNavigationRequest[] = [];
  readonly sessionCreateRequests: RouteDeckSessionCreateRequest[] = [];
  readonly privateValues = new Map<string, RouteDeckPrivateFormSnapshot>();
  readonly privateForms = {
    load: async (formId: string) => {
      this.calls.push(`private.load:${formId}`);
      const value = this.privateValues.get(formId);
      if (!value) throw new Error(`No scripted private form for ${formId}`);
      return structuredClone(value);
    },
    save: async (
      formId: string,
      request: {
        request_id: string;
        expected_session_version: number;
        value: JsonObject;
        complete?: boolean;
      },
    ): Promise<RouteDeckPrivateFormSaved> => {
      this.calls.push(`private.save:${formId}`);
      const previous = this.privateValues.get(formId);
      const saved: RouteDeckPrivateFormSnapshot = {
        form_id: formId,
        revision: (previous?.revision ?? 0) + 1,
        complete: request.complete ?? true,
        session_version: request.expected_session_version + 1,
        value: structuredClone(request.value),
      };
      this.privateValues.set(formId, saved);
      return {
        form_id: saved.form_id,
        revision: saved.revision,
        complete: saved.complete,
        session_version: saved.session_version,
        projection_version: 1,
      };
    },
  };

  private readonly sessionQueue: RouteDeckProjection[] = [];
  private readonly contractQueue: FrontendContract[] = [];
  private readonly createQueue: RouteDeckProjection[] = [];
  private readonly dispatchQueue: RouteDeckDispatchResult[] = [];
  private readonly navigationQueue: RouteDeckProjection[] = [];
  readonly dispatchRequests: RouteDeckDispatchRequest[] = [];
  private streamOptions: Omit<
    RouteDeckEventStreamOptions,
    "url" | "fetch" | "credentials"
  > | null = null;

  enqueueSession(projection: RouteDeckProjection): void {
    this.sessionQueue.push(projection);
  }

  enqueueFrontendContract(contract: FrontendContract): void {
    this.contractQueue.push(contract);
  }

  async getFrontendContract(): Promise<FrontendContract> {
    this.calls.push("contract.get");
    return take(this.contractQueue, "frontend contract");
  }

  enqueueCreatedSession(projection: RouteDeckProjection): void {
    this.createQueue.push(projection);
  }

  enqueueDispatch(result: RouteDeckDispatchResult): void {
    this.dispatchQueue.push(result);
  }

  enqueueNavigation(projection: RouteDeckProjection): void {
    this.navigationQueue.push(projection);
  }

  async createSession(
    request: RouteDeckSessionCreateRequest,
  ): Promise<RouteDeckProjection> {
    this.calls.push("session.create");
    this.sessionCreateRequests.push(structuredClone(request));
    return take(this.createQueue, "created session");
  }

  async getSession(): Promise<RouteDeckProjection> {
    this.calls.push("session.get");
    return take(this.sessionQueue, "session snapshot");
  }

  async navigate(request: RouteDeckNavigationRequest): Promise<RouteDeckProjection> {
    this.calls.push("navigation");
    this.navigationRequests.push(structuredClone(request));
    return take(this.navigationQueue, "navigation projection");
  }

  async dispatch(request: RouteDeckDispatchRequest): Promise<RouteDeckDispatchResult> {
    this.calls.push("dispatch");
    this.dispatchRequests.push(structuredClone(request));
    return take(this.dispatchQueue, "dispatch result");
  }

  async acceptReview(
    reviewId: string,
    _request: RouteDeckReviewRequest,
  ): Promise<RouteDeckDispatchResult> {
    this.calls.push(`review.accept:${reviewId}`);
    return take(this.dispatchQueue, "review result");
  }

  async rejectReview(
    reviewId: string,
    _request: RouteDeckReviewRequest,
  ): Promise<RouteDeckDispatchResult> {
    this.calls.push(`review.reject:${reviewId}`);
    return take(this.dispatchQueue, "review result");
  }

  async inspect(): Promise<RouteDeckInspection> {
    this.calls.push("inspect");
    throw new Error("No scripted inspection was provided.");
  }

  connectEvents(
    options: Omit<
      RouteDeckEventStreamOptions,
      "url" | "fetch" | "credentials"
    >,
  ): RouteDeckEventConnection {
    this.calls.push(`events.connect:${options.after}`);
    this.streamOptions = options;
    options.onOpen?.({ after: options.after, reconnecting: false });
    return {
      close: () => {
        if (this.streamOptions === options) this.streamOptions = null;
      },
      done: new Promise<void>(() => undefined),
    };
  }

  failStream(error: Parameters<NonNullable<RouteDeckEventStreamOptions["onError"]>>[0]): void {
    if (!this.streamOptions) throw new Error("No scripted event subscription is active.");
    this.streamOptions.onError?.(error);
  }

  reopenStream(): void {
    if (!this.streamOptions) throw new Error("No scripted event subscription is active.");
    this.streamOptions.onOpen?.({
      after: this.streamOptions.after,
      reconnecting: true,
    });
  }

  emit(event: RouteDeckEvent): void {
    if (!this.streamOptions) throw new Error("No scripted event subscription is active.");
    this.streamOptions.onEvent(event);
  }

  reset(requestedAfter: number, retainedFromCursor: number | null): void {
    if (!this.streamOptions) throw new Error("No scripted event subscription is active.");
    this.streamOptions.onReset({
      event_type: "stream_reset_required",
      requested_after: requestedAfter,
      retained_from_cursor: retainedFromCursor,
    });
  }
}

export class MemoryHistoryHarness implements RouteDeckHistoryAdapter {
  readonly entries: string[];
  readonly entryIds: Array<number | null>;
  private index: number;
  private readonly listeners = new Set<
    (path: string, historyEntryId: number | null) => void
  >();

  constructor(initial = "/") {
    this.entries = [initial];
    this.entryIds = [null];
    this.index = 0;
  }

  current(): string {
    const current = this.entries[this.index];
    if (current === undefined) throw new Error("History index is invalid.");
    return current;
  }

  currentEntryId(): number | null {
    return this.entryIds[this.index] ?? null;
  }

  push(path: string, historyEntryId: number): void {
    this.entries.splice(this.index + 1);
    this.entryIds.splice(this.index + 1);
    this.entries.push(path);
    this.entryIds.push(historyEntryId);
    this.index = this.entries.length - 1;
  }

  replace(path: string, historyEntryId: number): void {
    this.entries[this.index] = path;
    this.entryIds[this.index] = historyEntryId;
  }

  back(): void {
    if (this.index === 0) return;
    this.index -= 1;
    this.notifyCurrent();
  }

  forward(): void {
    if (this.index >= this.entries.length - 1) return;
    this.index += 1;
    this.notifyCurrent();
  }

  subscribe(listener: (path: string, historyEntryId: number | null) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  pop(path: string, historyEntryId: number): void {
    this.push(path, historyEntryId);
    this.notifyCurrent();
  }

  private notifyCurrent(): void {
    const path = this.current();
    const historyEntryId = this.currentEntryId();
    for (const listener of this.listeners) listener(path, historyEntryId);
  }
}

export async function flushRouteDeckTasks(turns = 8): Promise<void> {
  for (let index = 0; index < turns; index += 1) {
    await Promise.resolve();
  }
}

function take<T>(values: T[], label: string): T {
  const value = values.shift();
  if (value === undefined) throw new Error(`No scripted ${label} is available.`);
  return value;
}
