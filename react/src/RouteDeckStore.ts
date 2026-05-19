import type {
  RouteDeckClientState,
  RouteDeckDispatchInput,
  RouteDeckDispatchResult,
  RouteDeckEvent,
  RouteDeckInspectInput,
  RouteDeckIntrospection,
  RouteDeckProjection,
  RouteDeckRuntimeStatus,
  RouteDeckStore,
} from './types'

export interface EventSourceLike {
  addEventListener: (type: string, listener: (event: MessageEvent<string>) => void) => void
  close: () => void
}

export interface RouteDeckStoreConfig {
  initialState: RouteDeckClientState
  snapshot?: () => Promise<RouteDeckClientState | unknown>
  dispatch?: (input: RouteDeckDispatchInput, state: RouteDeckClientState) => Promise<RouteDeckDispatchResult | unknown>
  inspect?: (input?: RouteDeckInspectInput, state?: RouteDeckClientState) => Promise<RouteDeckIntrospection | unknown>
  snapshotUrl?: string | (() => string)
  dispatchUrl?: string | (() => string)
  inspectUrl?: string | (() => string)
  streamUrl?: string | (() => string)
  fetcher?: typeof fetch
  eventSourceFactory?: (url: string) => EventSourceLike
  mapSnapshot?: (payload: unknown) => RouteDeckClientState
  mapDispatchResult?: (payload: unknown, input: RouteDeckDispatchInput) => RouteDeckDispatchResult
  mapIntrospection?: (payload: unknown) => RouteDeckIntrospection
  buildDispatchRequest?: (input: RouteDeckDispatchInput, state: RouteDeckClientState) => unknown
}

const ROUTEDECK_EVENT_TYPES: RouteDeckEvent['event_type'][] = [
  'projection_update',
  'operation_started',
  'operation_completed',
  'graph_transition',
  'guard_failure',
  'surface_update',
  'runtime_status',
]

export function createRouteDeckStore(config: RouteDeckStoreConfig): RouteDeckStore {
  let state = normalizeState(config.initialState)
  const listeners = new Set<() => void>()

  const notify = () => {
    for (const listener of listeners) listener()
  }

  const setState = (next: RouteDeckClientState) => {
    state = normalizeState(next)
    notify()
  }

  const setStatus = (status: RouteDeckRuntimeStatus) => {
    state = { ...state, status }
    notify()
  }

  const applyEvent = (event: RouteDeckEvent) => {
    const payload = event.payload || {}
    const projection = payload.projection
    const eventStatus = payload.status
    const nextStatus = typeof eventStatus === 'string' ? (eventStatus as RouteDeckRuntimeStatus) : state.status
    if (event.event_type === 'projection_update' && isProjection(projection)) {
      setState({ ...state, projection, status: nextStatus, last_event: event })
      return
    }
    if (event.event_type === 'operation_completed' && isClientState(payload.state)) {
      setState({ ...payload.state, last_event: event })
      return
    }
    if (event.event_type === 'operation_completed' && isProjection(projection)) {
      setState({
        ...state,
        projection,
        status: nextStatus === 'dispatching' ? 'idle' : nextStatus,
        graph_state: isRecord(payload.state) ? payload.state : state.graph_state,
        location: typeof payload.replace_path === 'string' ? payload.replace_path : state.location,
        last_event: event,
      })
      return
    }
    if (event.event_type === 'runtime_status' && typeof eventStatus === 'string') {
      setState({ ...state, status: eventStatus as RouteDeckRuntimeStatus, last_event: event })
      return
    }
    setState({ ...state, last_event: event })
  }

  const store: RouteDeckStore = {
    getState: () => state,
    subscribe: (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    refresh: async () => {
      setStatus('refreshing')
      try {
        const payload = config.snapshot ? await config.snapshot() : await fetchJson(config, 'snapshotUrl')
        setState(mapSnapshot(config, payload))
      } catch (error) {
        state = { ...state, status: 'failed', metadata: { ...(state.metadata || {}), error } }
        notify()
        throw error
      }
    },
    dispatch: async (input) => {
      setStatus('dispatching')
      try {
        const payload = config.dispatch
          ? await config.dispatch(input, state)
          : await postJson(config, 'dispatchUrl', config.buildDispatchRequest?.(input, state) ?? input)
        const result = mapDispatchResult(config, payload, input)
        setState(result.state)
        return result
      } catch (error) {
        state = { ...state, status: 'failed', metadata: { ...(state.metadata || {}), error } }
        notify()
        throw error
      }
    },
    connectStream: () => {
      const url = resolveUrl(config.streamUrl)
      if (!url) return () => undefined
      const createSource = config.eventSourceFactory || ((sourceUrl: string) => new EventSource(sourceUrl))
      const source = createSource(url)
      const handleEvent = (event: MessageEvent<string>) => {
        const parsed = parseRouteDeckEvent(event.data)
        if (parsed) store.receiveEvent(parsed)
      }
      for (const eventType of ROUTEDECK_EVENT_TYPES) {
        source.addEventListener(eventType, handleEvent)
      }
      source.addEventListener('message', handleEvent)
      return () => source.close()
    },
    inspect: async (input) => {
      const payload = config.inspect
        ? await config.inspect(input, state)
        : await postJson(config, 'inspectUrl', input || {})
      return mapIntrospection(config, payload)
    },
    receiveEvent: applyEvent,
  }

  return store
}

export function createStaticRouteDeckStore(projection: RouteDeckProjection): RouteDeckStore {
  return createRouteDeckStore({
    initialState: {
      projection,
      status: 'idle',
      graph_state: {},
      location: null,
    },
    snapshot: async () => ({
      projection,
      status: 'idle',
      graph_state: {},
      location: null,
    }),
    dispatch: async (input, currentState) => ({
      operation_id: input.operation_id,
      accepted: false,
      state: currentState,
      messages: [],
      events: [],
      metadata: { reason: 'Static RouteDeck store cannot dispatch operations.' },
    }),
    inspect: async (input, currentState) => ({
      current_node: currentState?.projection.graph_node,
      reachable_nodes: [],
      legal_operations: currentState?.projection.legal_operations || [],
      blocked_operations: [],
      guard_explanations: [],
      surfaces: currentState?.projection.surfaces || {},
      route_traces: [],
      diagnostics: currentState?.projection.diagnostics || {},
    }),
  })
}

function normalizeState(next: RouteDeckClientState): RouteDeckClientState {
  return {
    ...next,
    status: next.status || 'idle',
    graph_state: next.graph_state || {},
    location: next.location ?? null,
    diagnostics: next.diagnostics || {},
    metadata: next.metadata || {},
  }
}

async function fetchJson(config: RouteDeckStoreConfig, key: 'snapshotUrl'): Promise<unknown> {
  const url = resolveUrl(config[key])
  if (!url) throw new Error(`RouteDeck store requires ${key}`)
  const fetcher = config.fetcher || fetch
  const response = await fetcher(url)
  if (!response.ok) throw new Error(`RouteDeck request failed: ${response.status}`)
  return response.json()
}

async function postJson(config: RouteDeckStoreConfig, key: 'dispatchUrl' | 'inspectUrl', body: unknown): Promise<unknown> {
  const url = resolveUrl(config[key])
  if (!url) throw new Error(`RouteDeck store requires ${key}`)
  const fetcher = config.fetcher || fetch
  const response = await fetcher(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(`RouteDeck request failed: ${response.status}`)
  return response.json()
}

function mapSnapshot(config: RouteDeckStoreConfig, payload: unknown): RouteDeckClientState {
  if (config.mapSnapshot) return config.mapSnapshot(payload)
  if (isClientState(payload)) return payload
  if (isProjection(payload)) return { projection: payload, status: 'idle' }
  if (payload && typeof payload === 'object') {
    const candidate = payload as { projection?: unknown; state?: unknown; replace_path?: unknown }
    if (isProjection(candidate.projection)) {
      return {
        projection: candidate.projection,
        status: 'idle',
        graph_state: isRecord(candidate.state) ? candidate.state : {},
        location: typeof candidate.replace_path === 'string' ? candidate.replace_path : null,
      }
    }
  }
  throw new Error('RouteDeck snapshot payload did not contain a projection.')
}

function mapDispatchResult(
  config: RouteDeckStoreConfig,
  payload: unknown,
  input: RouteDeckDispatchInput,
): RouteDeckDispatchResult {
  if (config.mapDispatchResult) return config.mapDispatchResult(payload, input)
  if (isDispatchResult(payload)) return payload
  if (payload && typeof payload === 'object') {
    const candidate = payload as { projection?: unknown; state?: unknown; replace_path?: unknown; active_surface?: unknown; messages?: unknown }
    if (isProjection(candidate.projection)) {
      return {
        operation_id: input.operation_id,
        accepted: true,
        state: {
          projection: candidate.projection,
          status: 'idle',
          graph_state: isRecord(candidate.state) ? candidate.state : {},
          location: typeof candidate.replace_path === 'string' ? candidate.replace_path : null,
        },
        active_surface: isRecord(candidate.active_surface) ? candidate.active_surface as never : null,
        messages: Array.isArray(candidate.messages) ? candidate.messages as Array<Record<string, unknown>> : [],
        events: [],
        metadata: {},
      }
    }
  }
  throw new Error('RouteDeck dispatch payload did not contain runtime state.')
}

function mapIntrospection(config: RouteDeckStoreConfig, payload: unknown): RouteDeckIntrospection {
  if (config.mapIntrospection) return config.mapIntrospection(payload)
  if (isRecord(payload) && isRecord(payload.snapshot) && isRecord(payload.snapshot.introspection)) {
    return payload.snapshot.introspection as unknown as RouteDeckIntrospection
  }
  if (isRecord(payload) && isRecord(payload.introspection)) {
    return payload.introspection as unknown as RouteDeckIntrospection
  }
  return isRecord(payload) ? payload as unknown as RouteDeckIntrospection : {}
}

function resolveUrl(value: string | (() => string) | undefined): string | null {
  if (!value) return null
  return typeof value === 'function' ? value() : value
}

function parseRouteDeckEvent(raw: string): RouteDeckEvent | null {
  try {
    const parsed = JSON.parse(raw) as RouteDeckEvent
    return parsed && typeof parsed.event_type === 'string' ? parsed : null
  } catch {
    return null
  }
}

function isProjection(value: unknown): value is RouteDeckProjection {
  if (!isRecord(value)) return false
  return typeof value.current_context === 'string' && typeof value.graph_node === 'string'
}

function isClientState(value: unknown): value is RouteDeckClientState {
  return isRecord(value) && isProjection(value.projection)
}

function isDispatchResult(value: unknown): value is RouteDeckDispatchResult {
  return isRecord(value) && typeof value.operation_id === 'string' && isClientState(value.state)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}
