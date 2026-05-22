import type { RouteDeckInvocationKind, RouteDeckOperation } from './types'

export function routeDeckOperationInteraction(operation: RouteDeckOperation): RouteDeckInvocationKind {
  if (operation.invocation_kind) return operation.invocation_kind
  if (operation.kind === 'form') return 'form'
  if ((operation.missing_args || []).length > 0) return 'entity_selector'
  return 'direct'
}

export function isRouteDeckOperationDispatchable(operation: RouteDeckOperation): boolean {
  if (operation.can_dispatch_now === false) return false
  const interaction = routeDeckOperationInteraction(operation)
  if (interaction !== 'direct' && interaction !== 'surface') return false
  return (operation.missing_args || []).length === 0
}
