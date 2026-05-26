import type {
  RouteDeckClientState,
  RouteDeckDispatchInput,
  RouteDeckDispatchResult,
  RouteDeckEvent,
  RouteDeckHistoryAdapter,
  RouteDeckInspectInput,
  RouteDeckIntrospection,
  RouteDeckLocationCodec,
  RouteDeckNavigationMode,
  RouteDeckLocation,
  RouteDeckPendingOperation,
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
  navigationMode?: RouteDeckNavigationMode
  locationCodec?: RouteDeckLocationCodec
  historyAdapter?: RouteDeckHistoryAdapter
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

  const setPendingOperation = (next: RouteDeckPendingOperation) => {
    state = { ...state, status: 'dispatching', pending_operation: next }
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
      if (isRouteDeckNavigationOperation(input.operation_id) && config.navigationMode !== 'remote') {
        const result = applyLocalNavigation(input.operation_id, input.args || {})
        setState(result.state)
        return result
      }
      setPendingOperation(pendingOperationForInput(input, state))
      try {
        const payload = config.dispatch
          ? await config.dispatch(input, state)
          : await postJson(config, 'dispatchUrl', config.buildDispatchRequest?.(input, state) ?? input)
        const result = mapDispatchResult(config, payload, input)
        setState({ ...result.state, pending_operation: null })
        return result
      } catch (error) {
        state = { ...state, status: 'failed', pending_operation: null, metadata: { ...(state.metadata || {}), error } }
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
    back: () => store.dispatch({ operation_id: 'route.back' }),
    forward: () => store.dispatch({ operation_id: 'route.forward' }),
    cancel: () => store.dispatch({ operation_id: 'route.cancel' }),
    openNode: (location) => store.dispatch({ operation_id: 'route.open_node', args: location as unknown as Record<string, unknown> }),
    switchSurface: (surfaceId) => store.dispatch({ operation_id: 'route.switch_surface', args: { surface_id: surfaceId } }),
  }

  const applyLocalNavigation = (operationId: string, args: Record<string, unknown>): RouteDeckDispatchResult => {
    const current = currentLocation(state)
    let navigation = state.projection.navigation
    let projection = state.projection
    let graphState = state.graph_state || {}

    if (operationId === 'route.switch_surface') {
      const surfaceId = String(args.surface_id || current.surface_id || '')
      const nextCurrent = { ...current, surface_id: surfaceId }
      navigation = navigationWithFlags({ ...navigation, current: nextCurrent })
      projection = withNavigation(withActiveSurfaceId(projection, surfaceId), navigation)
    } else if (operationId === 'route.open_node') {
      const next = locationFromArgs(args)
      navigation = navigationWithFlags({
        current: next,
        back_stack: [...navigation.back_stack, current],
        forward_stack: [],
      })
      projection = withNavigation(withProjectionNode(withActiveSurfaceId(projection, next.surface_id || ''), next.node_id), navigation)
      graphState = { ...graphState, node: next.node_id, route_params: next.params || {} }
    } else if (operationId === 'route.back') {
      const previous = navigation.back_stack.at(-1)
      if (previous) {
        navigation = navigationWithFlags({
          current: previous,
          back_stack: navigation.back_stack.slice(0, -1),
          forward_stack: [current, ...navigation.forward_stack],
        })
        projection = withNavigation(withProjectionNode(withActiveSurfaceId(projection, previous.surface_id || ''), previous.node_id), navigation)
        graphState = { ...graphState, node: previous.node_id, route_params: previous.params || {} }
      }
    } else if (operationId === 'route.forward') {
      const next = navigation.forward_stack[0]
      if (next) {
        navigation = navigationWithFlags({
          current: next,
          back_stack: [...navigation.back_stack, current],
          forward_stack: navigation.forward_stack.slice(1),
        })
        projection = withNavigation(withProjectionNode(withActiveSurfaceId(projection, next.surface_id || ''), next.node_id), navigation)
        graphState = { ...graphState, node: next.node_id, route_params: next.params || {} }
      }
    } else if (operationId === 'route.cancel') {
      const target = cancelTargetLocation(state) || navigation.back_stack.at(-1)
      if (target) {
        navigation = navigationWithFlags({
          current: target,
          back_stack: navigation.back_stack.filter((item) => item.node_id !== target.node_id),
          forward_stack: [current, ...navigation.forward_stack],
        })
        projection = withNavigation(withProjectionNode(withActiveSurfaceId(projection, target.surface_id || ''), target.node_id), navigation)
        graphState = { ...graphState, node: target.node_id, route_params: target.params || {} }
      }
    }

    return {
      operation_id: operationId,
      accepted: true,
      state: { ...state, projection, status: 'idle', graph_state: graphState, pending_operation: null },
      messages: [],
      events: [],
      metadata: { local_navigation: true },
    }
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
  const projection = normalizeProjection(next.projection)
  return {
    ...next,
    projection,
    status: next.status || 'idle',
    graph_state: next.graph_state || {},
    location: next.location ?? null,
    pending_operation: next.pending_operation ?? null,
    diagnostics: next.diagnostics || {},
    metadata: next.metadata || {},
  }
}

function normalizeProjection(projection: RouteDeckProjection): RouteDeckProjection {
  const navigation = navigationWithFlags(projection.navigation || {
    current: { node_id: projection.graph_node },
    back_stack: [],
    forward_stack: [],
  })
  return { ...projection, navigation }
}

function pendingOperationForInput(
  input: RouteDeckDispatchInput,
  currentState: RouteDeckClientState,
): RouteDeckPendingOperation {
  const operation = currentState.projection.legal_operations.find((candidate) => candidate.id === input.operation_id)
  const invocationKind = operation?.invocation_kind
  return {
    operation_id: input.operation_id,
    label: operation?.label || input.operation_id,
    invocation_kind: invocationKind,
    target_node: operation?.target_node || null,
    status: invocationKind === 'surface' ? 'opening_surface' : 'dispatching',
    started_at: Date.now(),
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

function isRouteDeckNavigationOperation(operationId: string) {
  return ['route.back', 'route.forward', 'route.cancel', 'route.open_node', 'route.switch_surface'].includes(operationId)
}

function currentLocation(state: RouteDeckClientState): RouteDeckLocation {
  const current = state.projection.navigation?.current
  return current?.node_id ? { ...current, params: current.params || {} } : { node_id: state.projection.graph_node }
}

function locationFromArgs(args: Record<string, unknown>): RouteDeckLocation {
  return {
    node_id: String(args.node_id || ''),
    surface_id: typeof args.surface_id === 'string' ? args.surface_id : null,
    params: isRecord(args.params) ? args.params : {},
  }
}

function navigationWithFlags(navigation: Partial<RouteDeckProjection['navigation']>): RouteDeckProjection['navigation'] {
  const current = navigation.current?.node_id ? navigation.current : { node_id: 'home' }
  const backStack = navigation.back_stack || []
  const forwardStack = navigation.forward_stack || []
  return {
    current,
    back_stack: backStack,
    forward_stack: forwardStack,
    can_back: backStack.length > 0,
    can_forward: forwardStack.length > 0,
    can_cancel: backStack.length > 0,
  }
}

function withNavigation(projection: RouteDeckProjection, navigation: RouteDeckProjection['navigation']): RouteDeckProjection {
  return { ...projection, navigation }
}

function withProjectionNode(projection: RouteDeckProjection, nodeId: string): RouteDeckProjection {
  if (!nodeId) return projection
  return { ...projection, graph_node: nodeId, current_context: nodeId }
}

function withActiveSurfaceId(projection: RouteDeckProjection, surfaceId: string): RouteDeckProjection {
  if (!surfaceId || !projection.surfaces.active) return projection
  const variant = surfaceId.split('.').at(-1) || projection.surfaces.active.variant
  return {
    ...projection,
    surfaces: {
      ...projection.surfaces,
      active: {
        ...projection.surfaces.active,
        surface_id: surfaceId,
        variant,
      },
    },
  }
}

function cancelTargetLocation(state: RouteDeckClientState): RouteDeckLocation | null {
  const hierarchy = state.projection.diagnostics?.node_hierarchy
  if (!isRecord(hierarchy)) return null
  const nodeMeta = hierarchy[state.projection.graph_node]
  if (!isRecord(nodeMeta) || typeof nodeMeta.cancel_target_node !== 'string') return null
  const targetMeta = hierarchy[nodeMeta.cancel_target_node]
  const targetSurfaceId = isRecord(targetMeta) && typeof targetMeta.default_surface_id === 'string'
    ? targetMeta.default_surface_id
    : null
  return {
    node_id: nodeMeta.cancel_target_node,
    surface_id: targetSurfaceId,
    params: {},
  }
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
