import assert from 'node:assert/strict'
import test from 'node:test'

import { assignDebuggerEdgeRoutes } from '../src/routeDeckDebuggerRouting.ts'

function layoutNode(id, x, y) {
  return { id, x, y, width: 178, height: 82 }
}

function routeIds(routes) {
  return Array.from(routes.entries())
    .sort(([leftId], [rightId]) => leftId.localeCompare(rightId))
    .map(([routeId, route]) => [routeId, route])
}

test('opposite-direction pair gets distinct routed geometry', () => {
  const nodes = [layoutNode('home', 0, 0), layoutNode('auth_register', 300, 0)]
  const edges = [
    { from: 'home', to: 'auth_register', type: 'transition', route_id: 'home->auth_register:0' },
    { from: 'auth_register', to: 'home', type: 'transition', route_id: 'auth_register->home:0' },
  ]

  const routes = assignDebuggerEdgeRoutes(nodes, edges)
  const forward = routes.get('home->auth_register:0')
  const backward = routes.get('auth_register->home:0')

  assert.ok(forward)
  assert.ok(backward)
  assert.notEqual(forward.pairOffset, backward.pairOffset)
  assert.notDeepEqual(forward.sourcePoint, backward.sourcePoint)
  assert.notDeepEqual(forward.targetPoint, backward.targetPoint)
})

test('multiple outgoing edges from one node get distinct source lanes', () => {
  const nodes = [
    layoutNode('hub', 0, 100),
    layoutNode('a', 300, 0),
    layoutNode('b', 300, 100),
    layoutNode('c', 300, 200),
  ]
  const edges = [
    { from: 'hub', to: 'a', type: 'transition', route_id: 'hub->a:0' },
    { from: 'hub', to: 'b', type: 'transition', route_id: 'hub->b:0' },
    { from: 'hub', to: 'c', type: 'transition', route_id: 'hub->c:0' },
  ]

  const routes = assignDebuggerEdgeRoutes(nodes, edges)
  const sourceOffsets = edges.map((edge) => routes.get(edge.route_id)?.sourceOffset)

  assert.equal(new Set(sourceOffsets).size, edges.length)
})

test('multiple incoming edges to one node get distinct target lanes', () => {
  const nodes = [
    layoutNode('a', 0, 0),
    layoutNode('b', 0, 100),
    layoutNode('c', 0, 200),
    layoutNode('hub', 300, 100),
  ]
  const edges = [
    { from: 'a', to: 'hub', type: 'transition', route_id: 'a->hub:0' },
    { from: 'b', to: 'hub', type: 'transition', route_id: 'b->hub:0' },
    { from: 'c', to: 'hub', type: 'transition', route_id: 'c->hub:0' },
  ]

  const routes = assignDebuggerEdgeRoutes(nodes, edges)
  const targetOffsets = edges.map((edge) => routes.get(edge.route_id)?.targetOffset)

  assert.equal(new Set(targetOffsets).size, edges.length)
})

test('lane assignment is deterministic for stable input', () => {
  const nodes = [
    layoutNode('home', 0, 0),
    layoutNode('auth_register', 300, -80),
    layoutNode('auth_sign_in', 300, 80),
    layoutNode('workspace', 620, 0),
  ]
  const edges = [
    { from: 'home', to: 'auth_register', type: 'transition', route_id: 'home->auth_register:0' },
    { from: 'home', to: 'auth_sign_in', type: 'transition', route_id: 'home->auth_sign_in:1' },
    { from: 'auth_register', to: 'workspace', type: 'transition', route_id: 'auth_register->workspace:2' },
    { from: 'auth_sign_in', to: 'workspace', type: 'transition', route_id: 'auth_sign_in->workspace:3' },
  ]

  const firstPass = routeIds(assignDebuggerEdgeRoutes(nodes, edges))
  const secondPass = routeIds(assignDebuggerEdgeRoutes(nodes, edges))

  assert.deepEqual(firstPass, secondPass)
})
