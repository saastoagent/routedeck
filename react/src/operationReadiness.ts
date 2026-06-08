import type { RouteDeckInvocationKind, RouteDeckOperation, RouteDeckProjection } from './types'

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

export interface RouteDeckAssistantActionOptions {
  includeCurrentNodeOperations?: boolean
  limit?: number
}

export function routeDeckAssistantActions(
  projection?: Pick<RouteDeckProjection, 'graph_node' | 'legal_operations'> | null,
  options: RouteDeckAssistantActionOptions = {},
): RouteDeckOperation[] {
  const currentNode = projection?.graph_node
  const operations = projection?.legal_operations || []
  const assistantActions = operations.filter((operation) => {
    if (operation.id.startsWith('route.')) return false
    if (operation.invocation_kind === 'hidden') return false
    if (operation.execution_mode === 'blocked') return false
    if (!isRouteDeckOperationDispatchable(operation)) return false
    if (
      !options.includeCurrentNodeOperations &&
      currentNode &&
      operation.target_node &&
      operation.target_node === currentNode
    ) {
      return false
    }
    return true
  })

  return typeof options.limit === 'number' ? assistantActions.slice(0, options.limit) : assistantActions
}
