import assert from 'node:assert/strict'
import test from 'node:test'

import { buildDebuggerRadialTopology } from '../src/routeDeckDebuggerTopology.ts'

function node(id, label, lane = 'main') {
  return { id, label, lane, allowed_actions: [] }
}

function edge(from, to, type = 'transition') {
  return { from, to, type }
}

function radialDistance(point) {
  return Math.hypot(point.x, point.y)
}

test('radial topology keeps home at the center and first-hop nodes on the primary ring', () => {
  const nodes = [
    node('home', 'Home', 'system'),
    node('auth_register', 'Register', 'auth'),
    node('auth_sign_in', 'Sign in', 'auth'),
    node('catalog', 'Catalog', 'catalog'),
    node('catalog_actions', 'Catalog Actions', 'catalog'),
  ]
  const edges = [
    edge('home', 'auth_register'),
    edge('home', 'auth_sign_in'),
    edge('home', 'catalog'),
    edge('catalog', 'catalog_actions'),
  ]

  const topology = buildDebuggerRadialTopology(nodes, edges, 'home')

  const home = topology.positions.get('home')
  const register = topology.positions.get('auth_register')
  const signIn = topology.positions.get('auth_sign_in')
  const catalog = topology.positions.get('catalog')
  const catalogActions = topology.positions.get('catalog_actions')

  assert.ok(home)
  assert.ok(register)
  assert.ok(signIn)
  assert.ok(catalog)
  assert.ok(catalogActions)
  assert.equal(home.x, 0)
  assert.equal(home.y, 0)
  assert.equal(topology.depthById.get('home'), 0)
  assert.equal(topology.depthById.get('catalog_actions'), 2)

  const registerRadius = radialDistance(register)
  const signInRadius = radialDistance(signIn)
  const catalogRadius = radialDistance(catalog)
  const catalogActionsRadius = radialDistance(catalogActions)

  assert.ok(Math.abs(registerRadius - signInRadius) < 2)
  assert.ok(Math.abs(registerRadius - catalogRadius) < 2)
  assert.ok(catalogActionsRadius > catalogRadius)
})

test('radial topology places disconnected components outside the reachable rings', () => {
  const nodes = [
    node('home', 'Home', 'system'),
    node('catalog', 'Catalog', 'catalog'),
    node('detached_root', 'Detached Root', 'memory'),
    node('detached_leaf', 'Detached Leaf', 'memory'),
  ]
  const edges = [
    edge('home', 'catalog'),
    edge('detached_root', 'detached_leaf'),
  ]

  const topology = buildDebuggerRadialTopology(nodes, edges, 'home')

  const catalog = topology.positions.get('catalog')
  const detachedRoot = topology.positions.get('detached_root')
  const detachedLeaf = topology.positions.get('detached_leaf')

  assert.ok(catalog)
  assert.ok(detachedRoot)
  assert.ok(detachedLeaf)
  assert.ok(radialDistance(detachedRoot) > radialDistance(catalog))
  assert.ok(radialDistance(detachedLeaf) > radialDistance(detachedRoot))
})
