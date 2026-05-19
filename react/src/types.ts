export interface RouteDeckActionField {
  key: string
  label: string
  field_type?: 'text' | 'password' | 'select' | 'url'
  required?: boolean
  placeholder?: string | null
  default?: unknown
  options?: { value: string; label: string }[] | null
  help_text?: string | null
  validation_hint?: string | null
  sensitive?: boolean
}

export interface RouteDeckActionCard {
  id: string
  label: string
  capability_id?: string | null
  description?: string | null
  emphasis?: 'primary' | 'secondary'
  kind?: 'button' | 'chip' | 'form' | 'nav' | 'summary'
  category?: 'auth' | 'setup' | 'navigation' | 'execution' | 'feedback' | 'learning'
  placement?: 'next_best' | 'rail' | 'inline' | 'evidence'
  fields?: RouteDeckActionField[]
  payload?: Record<string, unknown>
  recovery_prompt?: string | null
  disabled_reason?: string | null
}

export interface RouteDeckManifestNode {
  id: string
  label: string
  lane: string
  parent?: string | null
  description?: string | null
  prompt_placeholder?: string | null
  allowed_actions?: string[]
  expected_input?: string | null
  recovery_prompt?: string | null
}

export interface RouteDeckManifestEdge {
  from: string
  to: string
  type: string
  condition?: string | null
  explanation?: string | null
  action_id?: string | null
}

export interface RouteDeckManifestAction {
  id: string
  label: string
  capability_id?: string | null
  description?: string | null
  fields?: RouteDeckActionField[]
  allowed_nodes?: string[]
  visibility?: string
  recovery_prompt?: string | null
  sensitive?: boolean
}

export interface RouteDeckManifest {
  version: string
  nodes: RouteDeckManifestNode[]
  edges: RouteDeckManifestEdge[]
  actions?: RouteDeckManifestAction[]
  policies?: Record<string, unknown>
  test_paths?: Record<string, unknown>[]
}

export interface RouteDeckRuntimeSnapshot {
  current_node?: string | null
  reachable_nodes?: string[]
  valid_actions?: RouteDeckActionCard[]
  blocked_actions?: { id: string; reason: string }[]
  executed_nodes?: string[]
  progress?: Record<string, unknown>
  recovery_prompts?: string[]
  diagnostics?: Record<string, unknown>
}

export type RouteDeckSafetyClass =
  | 'navigation'
  | 'state_selection'
  | 'draft'
  | 'read_external'
  | 'write_external'
  | 'destructive'
  | 'credential'
  | 'admin'

export type RouteDeckExecutionMode = 'auto' | 'review' | 'blocked'
export type RouteDeckRuntimeStatus = 'idle' | 'refreshing' | 'streaming' | 'dispatching' | 'recovering' | 'failed'

export interface RouteDeckOperation {
  id: string
  label: string
  description?: string | null
  safety_class?: RouteDeckSafetyClass
  execution_mode?: RouteDeckExecutionMode
  input_schema?: Record<string, unknown>
  payload?: Record<string, unknown>
  guard?: string | null
  target_node?: string | null
}

export interface RouteDeckSurface {
  name: string
  component: string
  variant?: string
  role?: 'frame' | 'active' | 'diagnostic'
  props?: Record<string, unknown>
  lifecycle?: 'ephemeral' | 'stable'
}

export interface RouteDeckProjection {
  current_context: string
  graph_node: string
  projection_version: number
  legal_operations: RouteDeckOperation[]
  surfaces: Record<string, RouteDeckSurface>
  presentation_state: Record<string, unknown>
  diagnostics: Record<string, unknown>
}

export interface RouteDeckEvent {
  event_type:
    | 'projection_update'
    | 'operation_started'
    | 'operation_completed'
    | 'graph_transition'
    | 'guard_failure'
    | 'surface_update'
    | 'runtime_status'
  turn_id?: string | null
  projection_version?: number | null
  payload?: Record<string, unknown>
}

export interface RouteDeckClientState {
  projection: RouteDeckProjection
  status: RouteDeckRuntimeStatus
  graph_state?: Record<string, unknown>
  location?: string | null
  last_event?: RouteDeckEvent | null
  diagnostics?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export interface RouteDeckDispatchInput {
  operation_id: string
  args?: Record<string, unknown>
  graph_state?: Record<string, unknown>
  projection_version?: number | null
  context?: Record<string, unknown>
}

export interface RouteDeckDispatchResult {
  operation_id: string
  accepted: boolean
  state: RouteDeckClientState
  active_surface?: RouteDeckSurface | null
  messages?: Array<Record<string, unknown>>
  events?: RouteDeckEvent[]
  metadata?: Record<string, unknown>
}

export interface RouteDeckIntrospection {
  current_node?: string | null
  reachable_nodes?: string[]
  legal_operations?: Array<Record<string, unknown>>
  blocked_operations?: Array<Record<string, unknown>>
  guard_explanations?: string[]
  surfaces?: Record<string, unknown>
  route_traces?: Array<Record<string, unknown>>
  diagnostics?: Record<string, unknown>
}

export interface RouteDeckInspectInput {
  query?: string
  node_id?: string | null
  operation_id?: string | null
  context?: Record<string, unknown>
}

export interface RouteDeckStore {
  getState: () => RouteDeckClientState
  subscribe: (listener: () => void) => () => void
  refresh: () => Promise<void>
  dispatch: (input: RouteDeckDispatchInput) => Promise<RouteDeckDispatchResult>
  receiveEvent: (event: RouteDeckEvent) => void
  connectStream: () => () => void
  inspect: (input?: RouteDeckInspectInput) => Promise<RouteDeckIntrospection>
}
