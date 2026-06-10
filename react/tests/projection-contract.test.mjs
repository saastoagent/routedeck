import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { createRouteDeckStore } from '../src/RouteDeckStore.ts'

function legacyProjection() {
  return {
    current_context: 'detail',
    graph_node: 'detail',
    projection_version: 1,
    legal_operations: [],
    surfaces: {},
    presentation_state: {},
    diagnostics: {},
  }
}

test('old projection payloads normalize new reference fields to neutral defaults', () => {
  const store = createRouteDeckStore({
    initialState: {
      projection: legacyProjection(),
      status: 'idle',
    },
  })

  const projection = store.getState().projection
  assert.deepEqual(projection.capabilities, [])
  assert.deepEqual(projection.available_entities, [])
  assert.deepEqual(projection.surface_affordances, [])
  assert.deepEqual(projection.navgraph, {
    current: { node_id: 'detail', params: {} },
    nodes: [],
    edges: [],
    traversed: [],
    reachable: [],
  })
  assert.equal(projection.navigation.current.node_id, 'detail')
})

test('projection navgraph preserves location and node deeplinks', () => {
  const store = createRouteDeckStore({
    initialState: {
      projection: {
        ...legacyProjection(),
        navigation: {
          current: {
            node_id: 'detail',
            surface_id: 'review.detail',
            deeplink: { url: '/work/review/draft-alpha', resumable: true },
          },
          back_stack: [],
          forward_stack: [],
          can_back: false,
          can_forward: false,
          can_cancel: false,
        },
        navgraph: {
          current: {
            node_id: 'detail',
            surface_id: 'review.detail',
            deeplink: { url: '/work/review/draft-alpha', resumable: true },
          },
          nodes: [
            { id: 'queue', label: 'Queue', deeplink: { url: '/work/review', resumable: true } },
            { id: 'detail', label: 'Detail', deeplink: { url: '/work/review/draft-alpha', resumable: true } },
          ],
          edges: [{ from: 'queue', to: 'detail', action_id: 'review.open' }],
          traversed: ['queue'],
          reachable: ['queue'],
        },
      },
      status: 'idle',
    },
  })

  const projection = store.getState().projection
  assert.equal(projection.navigation.current.deeplink.url, '/work/review/draft-alpha')
  assert.equal(projection.navgraph.nodes[1].deeplink.url, '/work/review/draft-alpha')
})

test('surface interaction dispatch passes through without direct operation args', async () => {
  const calls = []
  const store = createRouteDeckStore({
    initialState: {
      projection: {
        ...legacyProjection(),
        surface_affordances: [
          {
            surface_id: 'review.detail',
            affordance_id: 'approve_primary',
            event: 'approve_clicked',
            operation_id: 'draft.approve',
            entity_keys: ['draft:alpha'],
          },
        ],
      },
      status: 'idle',
    },
    dispatch: async (input, state) => {
      calls.push(input)
      return {
        operation_id: 'draft.approve',
        accepted: true,
        state,
        messages: [],
        events: [],
        metadata: {},
      }
    },
  })

  await store.dispatch({
    surface_event: {
      surface_id: 'review.detail',
      affordance_id: 'approve_primary',
      event: 'click',
      entity_key: 'draft:alpha',
      payload: { decision: 'approve' },
    },
  })

  assert.equal(calls.length, 1)
  assert.deepEqual(calls[0], {
    surface_event: {
      surface_id: 'review.detail',
      affordance_id: 'approve_primary',
      event: 'click',
      entity_key: 'draft:alpha',
      payload: { decision: 'approve' },
    },
  })
})

test('React surface interaction event type includes emitted event name', () => {
  const source = readFileSync(new URL('../src/types.ts', import.meta.url), 'utf8')
  const match = source.match(/export interface RouteDeckSurfaceInteractionEvent \{(?<body>[\s\S]*?)\n\}/)

  assert.ok(match?.groups?.body)
  assert.match(match.groups.body, /event\?: string \| null/)
})

test('RouteDeckStore stream subscribes to framework events and applies projection updates', () => {
  const subscriptions = new Map()
  const source = {
    closed: false,
    addEventListener: (type, listener) => {
      subscriptions.set(type, listener)
    },
    close() {
      this.closed = true
    },
  }
  const nextProjection = {
    ...legacyProjection(),
    graph_node: 'detail',
    current_context: 'detail',
    projection_version: 2,
  }
  const store = createRouteDeckStore({
    initialState: {
      projection: legacyProjection(),
      status: 'idle',
    },
    streamUrl: '/events',
    eventSourceFactory: () => source,
  })

  const cleanup = store.connectStream()

  assert.deepEqual([...subscriptions.keys()].sort(), [
    'graph_transition',
    'guard_failure',
    'operation_completed',
    'operation_started',
    'projection_update',
    'runtime_status',
    'surface_update',
  ])

  subscriptions.get('projection_update')({
    data: JSON.stringify({
      event_type: 'projection_update',
      payload: { projection: nextProjection, status: 'refreshing' },
    }),
  })

  assert.equal(store.getState().projection.projection_version, 2)
  assert.equal(store.getState().status, 'refreshing')

  cleanup()
  assert.equal(source.closed, true)
})
