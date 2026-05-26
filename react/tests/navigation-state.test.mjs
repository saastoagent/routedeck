import assert from 'node:assert/strict'
import test from 'node:test'

import { readRouteDeckHistoryLocation, routeDeckUrlString, writeRouteDeckHistoryLocation } from '../src/RouteDeckLocation.ts'
import { resolveRouteDeckActiveSurface } from '../src/RouteDeckSurface.ts'
import { createRouteDeckStore } from '../src/RouteDeckStore.ts'

function projection(node = 'learning', surface = 'learning.policy_gaps') {
  return {
    current_context: node,
    graph_node: node,
    projection_version: 1,
    legal_operations: [],
    surfaces: {
      active: {
        name: 'active',
        surface_id: surface,
        component: 'LearningSurface',
        variant: surface.split('.').at(-1),
        role: 'active',
        slot: 'active',
        surface_kind: 'peer',
        label: 'Policy gaps',
        props: {},
      },
    },
    presentation_state: {},
    diagnostics: {},
    navigation: {
      current: { node_id: node, surface_id: surface },
      back_stack: [],
      forward_stack: [],
      can_back: false,
      can_forward: false,
      can_cancel: false,
    },
  }
}

test('route.switch_surface updates active surface without pushing history', async () => {
  const store = createRouteDeckStore({
    initialState: {
      projection: projection(),
      status: 'idle',
      graph_state: { node: 'learning' },
      location: '/app/agents/agent_1/learning',
    },
  })

  await store.dispatch({ operation_id: 'route.switch_surface', args: { surface_id: 'learning.failed_executions' } })

  const state = store.getState()
  assert.equal(state.projection.navigation.current.node_id, 'learning')
  assert.equal(state.projection.navigation.current.surface_id, 'learning.failed_executions')
  assert.equal(state.projection.navigation.back_stack.length, 0)
  assert.equal(state.projection.surfaces.active.surface_id, 'learning.failed_executions')
})

test('route.open_node pushes history and route.back restores previous location', async () => {
  const store = createRouteDeckStore({
    initialState: {
      projection: projection(),
      status: 'idle',
      graph_state: { node: 'learning' },
      location: '/app/agents/agent_1/learning',
    },
  })

  await store.dispatch({
    operation_id: 'route.open_node',
    args: {
      node_id: 'learning.policy_candidate',
      surface_id: 'learning.policy_candidate.review',
      params: { candidate_id: 'candidate_1' },
    },
  })

  assert.equal(store.getState().projection.graph_node, 'learning.policy_candidate')
  assert.equal(store.getState().projection.navigation.can_back, true)
  assert.equal(store.getState().projection.navigation.current.params.candidate_id, 'candidate_1')

  await store.dispatch({ operation_id: 'route.back' })

  assert.equal(store.getState().projection.graph_node, 'learning')
  assert.equal(store.getState().projection.navigation.current.surface_id, 'learning.policy_gaps')
  assert.equal(store.getState().projection.navigation.can_forward, true)
})

test('route.cancel returns to the declared cancel target', async () => {
  const store = createRouteDeckStore({
    initialState: {
      projection: {
        ...projection('learning.policy_candidate', 'learning.policy_candidate.review'),
        diagnostics: {
          node_hierarchy: {
            learning: { default_surface_id: 'learning.failed_executions' },
            'learning.policy_candidate': { cancel_target_node: 'learning' },
          },
        },
        navigation: {
          current: { node_id: 'learning.policy_candidate', surface_id: 'learning.policy_candidate.review' },
          back_stack: [{ node_id: 'learning', surface_id: 'learning.policy_gaps' }],
          forward_stack: [],
          can_back: true,
          can_forward: false,
          can_cancel: true,
        },
      },
      status: 'idle',
      graph_state: { node: 'learning.policy_candidate' },
      location: '/app/agents/agent_1/learning/policy-candidate/candidate_1',
    },
  })

  await store.dispatch({ operation_id: 'route.cancel' })

  assert.equal(store.getState().projection.graph_node, 'learning')
  assert.equal(store.getState().projection.navigation.current.node_id, 'learning')
  assert.equal(store.getState().projection.navigation.current.surface_id, 'learning.failed_executions')
})

test('remote navigation operations dispatch through the adapter instead of mutating locally', async () => {
  const calls = []
  const store = createRouteDeckStore({
    navigationMode: 'remote',
    initialState: {
      projection: {
        ...projection('learning.policy_candidate', 'learning.policy_candidate.review'),
        navigation: {
          current: { node_id: 'learning.policy_candidate', surface_id: 'learning.policy_candidate.review' },
          back_stack: [{ node_id: 'learning', surface_id: 'learning.policy_gaps' }],
          forward_stack: [],
          can_back: true,
          can_forward: false,
          can_cancel: true,
        },
      },
      status: 'idle',
      graph_state: { node: 'learning.policy_candidate' },
      location: '/app/agents/agent_1/learning/policy-candidate/candidate_1',
    },
    dispatch: async (input, state) => {
      calls.push({ input, state })
      return {
        operation_id: input.operation_id,
        accepted: true,
        state: {
          projection: projection('learning', 'learning.failed_executions'),
          status: 'idle',
          graph_state: { node: 'learning' },
          location: '/app/agents/agent_1/learning?surface=learning.failed_executions',
        },
        messages: [],
        events: [],
        metadata: { remote_navigation: true },
      }
    },
  })

  await store.back()

  assert.equal(calls.length, 1)
  assert.equal(calls[0].input.operation_id, 'route.back')
  assert.equal(store.getState().projection.graph_node, 'learning')
  assert.equal(store.getState().projection.navigation.current.surface_id, 'learning.failed_executions')
})

test('resolveRouteDeckActiveSurface prefers the navigation current surface id', () => {
  const current = resolveRouteDeckActiveSurface({
    ...projection(),
    surfaces: {
      active: {
        name: 'active',
        surface_id: 'learning.policy_gaps',
        component: 'LearningSurface',
        variant: 'policy_gaps',
        role: 'active',
        slot: 'active',
        surface_kind: 'peer',
        label: 'Policy gaps',
        props: {},
      },
      review: {
        name: 'review',
        surface_id: 'operation_review.execution.plan',
        component: 'CorpusOperationReviewSurface',
        variant: 'operation_review',
        role: 'active',
        slot: 'active',
        surface_kind: 'peer',
        label: 'Plan execution',
        props: {},
      },
    },
    navigation: {
      current: { node_id: 'learning', surface_id: 'operation_review.execution.plan' },
      back_stack: [],
      forward_stack: [],
      can_back: false,
      can_forward: false,
      can_cancel: false,
    },
  })

  assert.equal(current?.surface_id, 'operation_review.execution.plan')
  assert.equal(current?.component, 'CorpusOperationReviewSurface')
})

test('location codec and history adapter round-trip a generic RouteDeck location', () => {
  let currentUrl = { pathname: '/app/home', search: '', hash: '' }
  const adapter = {
    read: () => currentUrl,
    push: (nextUrl) => {
      currentUrl = nextUrl
    },
    replace: (nextUrl) => {
      currentUrl = nextUrl
    },
    subscribe: () => () => undefined,
  }
  const codec = {
    encode: (location) => ({
      pathname: `/app/${location.node_id}`,
      search: location.surface_id ? `?surface=${location.surface_id}` : '',
      hash: '',
    }),
    decode: (url) => ({
      node_id: url.pathname.split('/').at(-1) || 'home',
      surface_id: new URLSearchParams(url.search).get('surface'),
      params: {},
    }),
  }

  writeRouteDeckHistoryLocation({
    adapter,
    codec,
    location: {
      node_id: 'learning',
      surface_id: 'learning.failed_executions',
      params: {},
    },
    mode: 'push',
  })

  assert.equal(routeDeckUrlString(currentUrl), '/app/learning?surface=learning.failed_executions')
  assert.deepEqual(readRouteDeckHistoryLocation({ adapter, codec }), {
    node_id: 'learning',
    surface_id: 'learning.failed_executions',
    params: {},
  })
})
