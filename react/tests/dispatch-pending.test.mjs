import assert from 'node:assert/strict'
import test from 'node:test'

import { createRouteDeckStore } from '../src/RouteDeckStore.ts'

function projection() {
  return {
    current_context: 'home',
    graph_node: 'home',
    projection_version: 1,
    legal_operations: [
      {
        id: 'saas_agent.list',
        label: 'List SaaS Agents',
        invocation_kind: 'surface',
        target_node: 'saas_agent_select',
        can_dispatch_now: true,
      },
      {
        id: 'navigate.home',
        label: 'Home',
        invocation_kind: 'direct',
        target_node: 'home',
        can_dispatch_now: true,
      },
    ],
    surfaces: {},
    presentation_state: {},
    diagnostics: {},
  }
}

test('surface dispatch exposes pending opening state before the request resolves', async () => {
  let resolveDispatch
  const store = createRouteDeckStore({
    initialState: {
      projection: projection(),
      status: 'idle',
      graph_state: { node: 'home' },
      location: '/app/home',
    },
    dispatch: () =>
      new Promise((resolve) => {
        resolveDispatch = () =>
          resolve({
            operation_id: 'saas_agent.list',
            accepted: true,
            state: {
              projection: { ...projection(), graph_node: 'saas_agent_select', projection_version: 2 },
              status: 'idle',
              graph_state: { node: 'saas_agent_select' },
              location: '/app/agents',
            },
            messages: [],
            events: [],
            metadata: {},
          })
      }),
  })

  const dispatchPromise = store.dispatch({ operation_id: 'saas_agent.list', args: {} })
  const pending = store.getState().pending_operation

  assert.equal(store.getState().status, 'dispatching')
  assert.equal(pending?.operation_id, 'saas_agent.list')
  assert.equal(pending?.label, 'List SaaS Agents')
  assert.equal(pending?.status, 'opening_surface')
  assert.equal(pending?.target_node, 'saas_agent_select')

  resolveDispatch()
  await dispatchPromise

  assert.equal(store.getState().status, 'idle')
  assert.equal(store.getState().pending_operation, null)
})

test('direct dispatch exposes generic pending operation state', async () => {
  const store = createRouteDeckStore({
    initialState: {
      projection: projection(),
      status: 'idle',
      graph_state: { node: 'home' },
      location: '/app/home',
    },
    dispatch: async () => ({
      operation_id: 'navigate.home',
      accepted: true,
      state: {
        projection: projection(),
        status: 'idle',
        graph_state: { node: 'home' },
        location: '/app/home',
      },
      messages: [],
      events: [],
      metadata: {},
    }),
  })

  const dispatchPromise = store.dispatch({ operation_id: 'navigate.home', args: {} })
  const pending = store.getState().pending_operation

  assert.equal(pending?.operation_id, 'navigate.home')
  assert.equal(pending?.status, 'dispatching')

  await dispatchPromise
  assert.equal(store.getState().pending_operation, null)
})
