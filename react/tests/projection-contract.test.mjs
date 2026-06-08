import assert from 'node:assert/strict'
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
            surface_id: 'detail.product_detail',
            deeplink: { url: '/shop?rd_node=detail&rd_product=t-shirt', resumable: true },
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
            surface_id: 'detail.product_detail',
            deeplink: { url: '/shop?rd_node=detail&rd_product=t-shirt', resumable: true },
          },
          nodes: [
            { id: 'browse', label: 'Browse', deeplink: { url: '/shop?rd_node=browse', resumable: true } },
            { id: 'detail', label: 'Detail', deeplink: { url: '/shop?rd_node=detail&rd_product=t-shirt', resumable: true } },
          ],
          edges: [{ from: 'browse', to: 'detail', action_id: 'catalog.open' }],
          traversed: ['browse'],
          reachable: ['browse'],
        },
      },
      status: 'idle',
    },
  })

  const projection = store.getState().projection
  assert.equal(projection.navigation.current.deeplink.url, '/shop?rd_node=detail&rd_product=t-shirt')
  assert.equal(projection.navgraph.nodes[1].deeplink.url, '/shop?rd_node=detail&rd_product=t-shirt')
})

test('surface interaction dispatch passes through without direct operation args', async () => {
  const calls = []
  const store = createRouteDeckStore({
    initialState: {
      projection: {
        ...legacyProjection(),
        surface_affordances: [
          {
            surface_id: 'detail.product_detail',
            affordance_id: 'add_to_cart',
            event: 'add_clicked',
            operation_id: 'cart.add_item',
            entity_keys: ['variant:s-black'],
          },
        ],
      },
      status: 'idle',
    },
    dispatch: async (input, state) => {
      calls.push(input)
      return {
        operation_id: 'cart.add_item',
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
      surface_id: 'detail.product_detail',
      affordance_id: 'add_to_cart',
      entity_key: 'variant:s-black',
      payload: { quantity: 1 },
    },
  })

  assert.equal(calls.length, 1)
  assert.deepEqual(calls[0], {
    surface_event: {
      surface_id: 'detail.product_detail',
      affordance_id: 'add_to_cart',
      entity_key: 'variant:s-black',
      payload: { quantity: 1 },
    },
  })
})
