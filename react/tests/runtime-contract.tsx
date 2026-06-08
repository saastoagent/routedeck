import { createElement } from 'react'
import {
  RouteDeckProvider,
  useRouteDeckAvailableEntities,
  useRouteDeckCapabilities,
  useRouteDeckSurfaceAffordances,
  useRouteDeckOperation,
  useRouteDeckOperations,
  useRouteDeckProjection,
  useRouteDeckSurface,
  type RouteDeckAvailableEntity,
  type RouteDeckCapabilitySpec,
  type RouteDeckProjection,
  type RouteDeckSurfaceAffordance,
} from '../src'

const projection: RouteDeckProjection = {
  current_context: 'dashboard',
  graph_node: 'dashboard',
  projection_version: 1,
  legal_operations: [
    {
      id: 'workflow.create',
      label: 'Create workflow',
      safety_class: 'navigation',
      execution_mode: 'auto',
      capability_id: 'workflow.create',
    },
  ],
  capabilities: [
    {
      capability_id: 'workflow.create',
      label: 'Create workflow',
      operation_ids: ['workflow.create'],
      entity_kinds: ['workflow'],
      surface_ids: ['dashboard.main'],
    } satisfies RouteDeckCapabilitySpec,
  ],
  available_entities: [
    {
      kind: 'workflow',
      entity_key: 'workflow:new',
      label: 'New workflow',
      rendered_on: ['dashboard.main'],
      operations: [{ operation_id: 'workflow.create', args: { template_ref: 'template_opaque_1' } }],
    } satisfies RouteDeckAvailableEntity,
  ],
  surface_affordances: [
    {
      surface_id: 'dashboard.main',
      affordance_id: 'create_workflow',
      event: 'create_clicked',
      capability_id: 'workflow.create',
      operation_id: 'workflow.create',
      entity_key: 'workflow:new',
    } satisfies RouteDeckSurfaceAffordance,
  ],
  surfaces: {
    main: {
      name: 'main',
      surface_id: 'dashboard.main',
      component: 'DashboardPanel',
      variant: 'default',
      role: 'frame',
      props: { count: 1 },
    },
  },
  presentation_state: {},
  diagnostics: {},
}

function RuntimeConsumer() {
  const current = useRouteDeckProjection()
  const main = useRouteDeckSurface('main')
  const operations = useRouteDeckOperations()
  const createOperation = useRouteDeckOperation('workflow.create')
  const capabilities = useRouteDeckCapabilities()
  const entities = useRouteDeckAvailableEntities()
  const affordances = useRouteDeckSurfaceAffordances('dashboard.main')

  return createElement('pre', null, [
    current.graph_node,
    main?.component,
    operations.length,
    createOperation?.execution_mode,
    capabilities[0]?.capability_id,
    entities[0]?.entity_key,
    affordances[0]?.affordance_id,
  ].join(':'))
}

createElement(
  RouteDeckProvider,
  {
    initialProjection: projection,
  },
  createElement(RuntimeConsumer),
)
