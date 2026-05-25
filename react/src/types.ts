export interface RouteDeckActionField {
  key: string
  label: string
  field_type?: 'text' | 'password' | 'select' | 'url' | 'textarea'
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
  node_kind?: 'workflow' | 'section' | 'detail' | 'transient'
  capability_id?: string | null
  show_in_navgraph?: boolean
  show_in_capability_rail?: boolean
  cancel_target_node?: string | null
  dirty_policy?: 'none' | 'confirm' | 'block'
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
export type RouteDeckInvocationKind = 'direct' | 'form' | 'entity_selector' | 'surface' | 'hidden'
export type RouteDeckRuntimeStatus = 'idle' | 'refreshing' | 'streaming' | 'dispatching' | 'recovering' | 'failed'

export interface RouteDeckOperation {
  id: string
  label: string
  description?: string | null
  category?: 'auth' | 'setup' | 'navigation' | 'execution' | 'feedback' | 'learning' | null
  kind?: 'button' | 'chip' | 'form' | 'nav' | 'summary' | null
  placement?: 'next_best' | 'rail' | 'inline' | 'evidence' | null
  emphasis?: 'primary' | 'secondary'
  safety_class?: RouteDeckSafetyClass
  execution_mode?: RouteDeckExecutionMode
  input_schema?: Record<string, unknown>
  payload?: Record<string, unknown>
  invocation_kind?: RouteDeckInvocationKind
  can_dispatch_now?: boolean
  required_args?: string[]
  missing_args?: string[]
  guard?: string | null
  target_node?: string | null
}

export interface RouteDeckSurface {
  name: string
  surface_id?: string | null
  component: string
  variant?: string
  role?: 'frame' | 'active' | 'diagnostic'
  slot?: string | null
  surface_kind?: 'peer' | 'detail' | 'embedded'
  label?: string | null
  default?: boolean
  props?: Record<string, unknown>
  lifecycle?: 'ephemeral' | 'stable'
}

export interface RouteDeckLocation {
  node_id: string
  surface_id?: string | null
  params?: Record<string, unknown>
}

export interface RouteDeckNavigationState {
  current: RouteDeckLocation
  back_stack: RouteDeckLocation[]
  forward_stack: RouteDeckLocation[]
  can_back: boolean
  can_forward: boolean
  can_cancel: boolean
}

export interface RouteDeckProjection {
  current_context: string
  graph_node: string
  projection_version: number
  legal_operations: RouteDeckOperation[]
  surfaces: Record<string, RouteDeckSurface>
  presentation_state: Record<string, unknown>
  navigation: RouteDeckNavigationState
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
  pending_operation?: RouteDeckPendingOperation | null
  diagnostics?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export interface RouteDeckPendingOperation {
  operation_id: string
  label: string
  invocation_kind?: RouteDeckInvocationKind
  target_node?: string | null
  status: 'dispatching' | 'opening_surface'
  started_at: number
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
  back: () => Promise<RouteDeckDispatchResult>
  forward: () => Promise<RouteDeckDispatchResult>
  cancel: () => Promise<RouteDeckDispatchResult>
  openNode: (location: RouteDeckLocation) => Promise<RouteDeckDispatchResult>
  switchSurface: (surfaceId: string) => Promise<RouteDeckDispatchResult>
}
