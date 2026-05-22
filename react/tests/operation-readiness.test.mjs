import assert from 'node:assert/strict'
import test from 'node:test'

import {
  isRouteDeckOperationDispatchable,
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
