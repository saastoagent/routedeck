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
