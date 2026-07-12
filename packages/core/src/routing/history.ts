export interface RouteDeckHistoryAdapter {
  current(): string;
  currentEntryId(): number | null;
  push(path: string, historyEntryId: number): void;
  replace(path: string, historyEntryId: number): void;
  back(): void;
  forward(): void;
  subscribe(listener: (path: string, historyEntryId: number | null) => void): () => void;
}

export interface BrowserHistoryTarget {
  location: Pick<Location, "pathname" | "search">;
  history: Pick<
    History,
    "pushState" | "replaceState" | "back" | "forward" | "state"
  >;
  addEventListener(type: "popstate", listener: () => void): void;
  removeEventListener(type: "popstate", listener: () => void): void;
}

export function createBrowserHistoryAdapter(
  target: BrowserHistoryTarget,
): RouteDeckHistoryAdapter {
  const read = () => `${target.location.pathname}${target.location.search}`;
  const readEntryId = () => decodeHistoryEntryId(target.history.state);
  return {
    current: read,
    currentEntryId: readEntryId,
    push(path, historyEntryId) {
      target.history.pushState(encodeHistoryState(historyEntryId), "", path);
    },
    replace(path, historyEntryId) {
      target.history.replaceState(encodeHistoryState(historyEntryId), "", path);
    },
    back() {
      target.history.back();
    },
    forward() {
      target.history.forward();
    },
    subscribe(listener) {
      const onPopState = () => listener(read(), readEntryId());
      target.addEventListener("popstate", onPopState);
      return () => target.removeEventListener("popstate", onPopState);
    },
  };
}

function encodeHistoryState(historyEntryId: number): object {
  if (!Number.isSafeInteger(historyEntryId) || historyEntryId < 1) {
    throw new TypeError("RouteDeck history entry IDs must be positive safe integers.");
  }
  return Object.freeze({
    routedeck: Object.freeze({ version: 1, history_entry_id: historyEntryId }),
  });
}

function decodeHistoryEntryId(value: unknown): number | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  const outer = value as Record<string, unknown>;
  if (Object.keys(outer).length !== 1) return null;
  const routeDeck = outer.routedeck;
  if (routeDeck === null || typeof routeDeck !== "object" || Array.isArray(routeDeck)) {
    return null;
  }
  const state = routeDeck as Record<string, unknown>;
  if (
    Object.keys(state).length !== 2 ||
    state.version !== 1 ||
    !Number.isSafeInteger(state.history_entry_id) ||
    (state.history_entry_id as number) < 1
  ) {
    return null;
  }
  return state.history_entry_id as number;
}
