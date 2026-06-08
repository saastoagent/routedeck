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
  category?: 'auth' | 'setup' | 'navigation' | 'execution' | 'feedback' | 'learning' | 'deployment'
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
  capability_id?: string | null
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
  capabilities?: RouteDeckCapabilitySpec[]
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
export type RouteDeckNavigationMode = 'local' | 'remote'

export interface RouteDeckOperation {
  id: string
  label: string
  description?: string | null
  category?: 'auth' | 'setup' | 'navigation' | 'execution' | 'feedback' | 'learning' | 'deployment' | null
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
  capability_id?: string | null
  surface_id?: string | null
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
  deeplink?: RouteDeckDeepLink | null
}

export interface RouteDeckUrl {
  pathname: string
  search?: string
  hash?: string
}

export interface RouteDeckDeepLink {
  url: string
  resumable?: boolean
  requires_auth?: boolean
  label?: string | null
}

export interface RouteDeckLocationCodec {
  encode: (location: RouteDeckLocation) => RouteDeckUrl
  decode: (url: RouteDeckUrl) => RouteDeckLocation | null
}

export interface RouteDeckHistoryAdapter {
  read: () => RouteDeckUrl
  push: (url: RouteDeckUrl) => void
  replace: (url: RouteDeckUrl) => void
  subscribe: (listener: () => void) => () => void
}

export interface RouteDeckNavigationState {
  current: RouteDeckLocation
  back_stack: RouteDeckLocation[]
  forward_stack: RouteDeckLocation[]
  can_back: boolean
  can_forward: boolean
  can_cancel: boolean
}

export interface RouteDeckCapabilitySpec {
  capability_id: string
  label: string
  operation_ids?: string[]
  entity_kinds?: string[]
  surface_ids?: string[]
  chat_enabled?: boolean
  surface_enabled?: boolean
  description?: string | null
  metadata?: Record<string, unknown>
}

export interface RouteDeckEntityOperationBinding {
  operation_id: string
  args?: Record<string, unknown>
}

export interface RouteDeckAvailableEntity {
  kind: string
  entity_key: string
  label: string
  parent_label?: string | null
  rendered_on?: string[]
  operations?: RouteDeckEntityOperationBinding[]
  metadata?: Record<string, unknown>
}

export interface RouteDeckBindingExpression {
  from: 'entity' | 'event'
  path: string
}

export interface RouteDeckSurfaceAffordance {
  surface_id: string
  affordance_id: string
  event: string
  capability_id?: string | null
  operation_id?: string | null
  entity_key?: string | null
  entity_keys?: string[]
  arg_bindings?: Record<string, RouteDeckBindingExpression>
  metadata?: Record<string, unknown>
}

export interface RouteDeckSurfaceInteractionEvent {
  surface_id: string
  affordance_id: string
  entity_key?: string | null
  payload?: Record<string, unknown>
}

export interface RouteDeckSemanticObservation {
  type: string
  summary: string
  entity_key?: string | null
  operation_id?: string | null
  accepted?: boolean | null
  metadata?: Record<string, unknown>
}

export interface RouteDeckNavGraphNode {
  id: string
  label: string
  surface_id?: string | null
  deeplink?: RouteDeckDeepLink | null
  capability_ids?: string[]
  metadata?: Record<string, unknown>
}

export interface RouteDeckNavGraphEdge {
  from: string
  to: string
  action_id?: string | null
  capability_id?: string | null
  metadata?: Record<string, unknown>
}

export interface RouteDeckNavGraph {
  current: RouteDeckLocation
  nodes?: RouteDeckNavGraphNode[]
  edges?: RouteDeckNavGraphEdge[]
  traversed?: string[]
  reachable?: string[]
}

export interface RouteDeckProjection {
  current_context: string
  graph_node: string
  projection_version: number
  legal_operations: RouteDeckOperation[]
  surfaces: Record<string, RouteDeckSurface>
  presentation_state: Record<string, unknown>
  navigation: RouteDeckNavigationState
  capabilities?: RouteDeckCapabilitySpec[]
  navgraph?: RouteDeckNavGraph | null
  available_entities?: RouteDeckAvailableEntity[]
  surface_affordances?: RouteDeckSurfaceAffordance[]
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
  operation_id?: string | null
  surface_event?: RouteDeckSurfaceInteractionEvent | null
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
