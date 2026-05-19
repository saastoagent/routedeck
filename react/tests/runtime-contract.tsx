import { createElement } from 'react'
import {
  RouteDeckProvider,
  useRouteDeckOperation,
  useRouteDeckOperations,
  useRouteDeckProjection,
  useRouteDeckSurface,
  type RouteDeckProjection,
} from '../src'

const projection: RouteDeckProjection = {
  current_context: 'dashboard',
  graph_node: 'dashboard',
  projection_version: 1,
  legal_operations: [
    {
      id: 'agent.create',
      label: 'Create SaaS Agent',
      safety_class: 'navigation',
      execution_mode: 'auto',
    },
  ],
  surfaces: {
    main: {
      name: 'main',
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
  const createOperation = useRouteDeckOperation('agent.create')

  return createElement('pre', null, [
    current.graph_node,
    main?.component,
    operations.length,
    createOperation?.execution_mode,
  ].join(':'))
}

createElement(
  RouteDeckProvider,
  {
    initialProjection: projection,
  },
  createElement(RuntimeConsumer),
)
