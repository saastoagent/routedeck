import assert from 'node:assert/strict'
import test from 'node:test'

import {
  isRouteDeckOperationDispatchable,
  routeDeckAssistantActions,
  routeDeckOperationInteraction,
} from '../src/operationReadiness.ts'

test('required unbound args make an operation legal but not directly dispatchable', () => {
  const operation = {
    id: 'draft.open',
    label: 'Open draft',
    invocation_kind: 'entity_selector',
    required_args: ['draft_ref'],
    missing_args: ['draft_ref'],
    can_dispatch_now: false,
  }

  assert.equal(isRouteDeckOperationDispatchable(operation), false)
  assert.equal(routeDeckOperationInteraction(operation), 'entity_selector')
})

test('bound entity operation can be dispatched directly', () => {
  const operation = {
    id: 'draft.open',
    label: 'Open draft',
    invocation_kind: 'direct',
    required_args: ['draft_ref'],
    missing_args: [],
    can_dispatch_now: true,
    payload: { draft_ref: 'draft-1' },
  }

  assert.equal(isRouteDeckOperationDispatchable(operation), true)
  assert.equal(routeDeckOperationInteraction(operation), 'direct')
})

test('assistant actions hide internal, unbound, and current-node no-op operations', () => {
  const projection = {
    graph_node: 'queue',
    legal_operations: [
      {
        id: 'review.queue',
        label: 'Review queue',
        invocation_kind: 'direct',
        can_dispatch_now: true,
        target_node: 'queue',
      },
      {
        id: 'review.open',
        label: 'Open review',
        invocation_kind: 'entity_selector',
        can_dispatch_now: false,
        missing_args: ['entity_key'],
      },
      {
        id: 'review.summary',
        label: 'View summary',
        invocation_kind: 'direct',
        can_dispatch_now: true,
        target_node: 'summary',
      },
      {
        id: 'route.open_node',
        label: 'Open node',
        invocation_kind: 'hidden',
        can_dispatch_now: true,
      },
    ],
  }

  assert.deepEqual(routeDeckAssistantActions(projection).map((operation) => operation.id), ['review.summary'])
})

test('assistant action current-node filtering can be explicitly relaxed', () => {
  const projection = {
    graph_node: 'queue',
    legal_operations: [
      {
        id: 'review.queue',
        label: 'Refresh queue',
        invocation_kind: 'direct',
        can_dispatch_now: true,
        target_node: 'queue',
      },
    ],
  }

  assert.deepEqual(
    routeDeckAssistantActions(projection, { includeCurrentNodeOperations: true }).map((operation) => operation.id),
    ['review.queue'],
  )
})
