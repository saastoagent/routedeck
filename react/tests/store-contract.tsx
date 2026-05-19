import { createElement } from 'react'
import {
  RouteDeckProvider,
  createRouteDeckStore,
  useRouteDeckDispatch,
  useRouteDeckInspect,
  useRouteDeckProjection,
  useRouteDeckStatus,
  useRouteDeckState,
  useRouteDeckStore,
  type RouteDeckClientState,
  type RouteDeckDispatchInput,
  type RouteDeckDispatchResult,
  type RouteDeckIntrospection,
  type RouteDeckProjection,
} from '../src'

const initialProjection: RouteDeckProjection = {
  current_context: 'home',
  graph_node: 'home',
  projection_version: 1,
  legal_operations: [],
  surfaces: {},
  presentation_state: {},
  diagnostics: {},
}

const refreshedProjection: RouteDeckProjection = {
  ...initialProjection,
  graph_node: 'dashboard',
  projection_version: 2,
}

const store = createRouteDeckStore({
  initialState: {
    projection: initialProjection,
    status: 'idle',
    graph_state: { node: 'home' },
    location: '/app/home',
  },
  snapshot: async (): Promise<RouteDeckClientState> => ({
    projection: refreshedProjection,
    status: 'idle',
    graph_state: { node: 'dashboard' },
    location: '/app/home',
  }),
  dispatch: async (input: RouteDeckDispatchInput): Promise<RouteDeckDispatchResult> => ({
    operation_id: input.operation_id,
    accepted: true,
    state: {
      projection: refreshedProjection,
      status: 'idle',
      graph_state: { node: 'dashboard' },
      location: '/app/home',
    },
    messages: [],
    events: [],
    metadata: {},
  }),
  inspect: async (): Promise<RouteDeckIntrospection> => ({
    current_node: 'dashboard',
    reachable_nodes: [],
    legal_operations: [],
    blocked_operations: [],
    guard_explanations: [],
    surfaces: {},
    route_traces: [],
    diagnostics: {},
  }),
})

store.subscribe(() => {
  const state = store.getState()
  state.projection.graph_node.toUpperCase()
})

await store.refresh()
store.receiveEvent({ event_type: 'projection_update', payload: { projection: refreshedProjection } })
await store.dispatch({ operation_id: 'navigate.dashboard', args: {}, graph_state: { node: 'home' } })
await store.inspect({})

function StoreConsumer() {
  const current = useRouteDeckProjection()
  const status = useRouteDeckStatus()
  const dispatch = useRouteDeckDispatch()
  const inspect = useRouteDeckInspect()
  const currentStore = useRouteDeckStore()
  const runtimeState = useRouteDeckState()

  dispatch({ operation_id: 'navigate.dashboard' })
  inspect({})

  return createElement('pre', null, [current.graph_node, status, runtimeState.location, currentStore.getState().location].join(':'))
}

createElement(RouteDeckProvider, { store }, createElement(StoreConsumer))
createElement(RouteDeckProvider, { initialProjection }, createElement(StoreConsumer))
