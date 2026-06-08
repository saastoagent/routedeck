import assert from 'node:assert/strict'
import test from 'node:test'

import {
  isRouteDeckOperationDispatchable,
  routeDeckAssistantActions,
  routeDeckOperationInteraction,
} from '../src/operationReadiness.ts'

test('required unbound args make an operation legal but not directly dispatchable', () => {
  const operation = {
    id: 'saas_agent.open',
    label: 'Open SaaS Agent',
    invocation_kind: 'entity_selector',
    required_args: ['saas_agent_id'],
    missing_args: ['saas_agent_id'],
    can_dispatch_now: false,
  }

  assert.equal(isRouteDeckOperationDispatchable(operation), false)
  assert.equal(routeDeckOperationInteraction(operation), 'entity_selector')
})

test('bound entity operation can be dispatched directly', () => {
  const operation = {
    id: 'saas_agent.open',
    label: 'Open SaaS Agent',
    invocation_kind: 'direct',
    required_args: ['saas_agent_id'],
    missing_args: [],
    can_dispatch_now: true,
    payload: { saas_agent_id: 'agent-1' },
  }

  assert.equal(isRouteDeckOperationDispatchable(operation), true)
  assert.equal(routeDeckOperationInteraction(operation), 'direct')
})

test('assistant actions hide internal, unbound, and current-node no-op operations', () => {
  const projection = {
    graph_node: 'browse',
    legal_operations: [
      {
        id: 'catalog.list',
        label: 'Browse products',
        invocation_kind: 'direct',
        can_dispatch_now: true,
        target_node: 'browse',
      },
      {
        id: 'catalog.open',
        label: 'View product',
        invocation_kind: 'entity_selector',
        can_dispatch_now: false,
        missing_args: ['entity_key'],
      },
      {
        id: 'cart.view',
        label: 'View cart',
        invocation_kind: 'direct',
        can_dispatch_now: true,
        target_node: 'cart',
      },
      {
        id: 'route.open_node',
        label: 'Open node',
        invocation_kind: 'hidden',
        can_dispatch_now: true,
      },
    ],
  }

  assert.deepEqual(routeDeckAssistantActions(projection).map((operation) => operation.id), ['cart.view'])
})

test('assistant action current-node filtering can be explicitly relaxed', () => {
  const projection = {
    graph_node: 'browse',
    legal_operations: [
      {
        id: 'catalog.list',
        label: 'Refresh products',
        invocation_kind: 'direct',
        can_dispatch_now: true,
        target_node: 'browse',
      },
    ],
  }

  assert.deepEqual(
    routeDeckAssistantActions(projection, { includeCurrentNodeOperations: true }).map((operation) => operation.id),
    ['catalog.list'],
  )
})
