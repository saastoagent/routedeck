import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from 'react'

import { createStaticRouteDeckStore } from './RouteDeckStore'
import type {
  RouteDeckClientState,
  RouteDeckDispatchInput,
  RouteDeckDispatchResult,
  RouteDeckEvent,
  RouteDeckInspectInput,
  RouteDeckIntrospection,
  RouteDeckOperation,
  RouteDeckPendingOperation,
  RouteDeckProjection,
  RouteDeckStore,
  RouteDeckSurface,
} from './types'

interface RouteDeckContextValue {
  store: RouteDeckStore
  state: RouteDeckClientState
}

export interface RouteDeckProviderProps {
  children: ReactNode
  store?: RouteDeckStore
  initialProjection?: RouteDeckProjection
}

const RouteDeckContext = createContext<RouteDeckContextValue | null>(null)

export function RouteDeckProvider({
  children,
  store,
  initialProjection,
}: RouteDeckProviderProps) {
  const resolvedStore = useMemo(() => {
    if (store) return store
    if (initialProjection) return createStaticRouteDeckStore(initialProjection)
    throw new Error('RouteDeckProvider requires a store or initialProjection')
  }, [initialProjection, store])

  const state = useSyncExternalStore(
    resolvedStore.subscribe,
    resolvedStore.getState,
    resolvedStore.getState,
  )

  useEffect(() => resolvedStore.connectStream(), [resolvedStore])

  const value = useMemo(() => ({ store: resolvedStore, state }), [resolvedStore, state])

  return <RouteDeckContext.Provider value={value}>{children}</RouteDeckContext.Provider>
}

export function useRouteDeckStore(): RouteDeckStore {
  return useRouteDeckContext().store
}

export function useRouteDeckState(): RouteDeckClientState {
  return useRouteDeckContext().state
}

export function useRouteDeckProjection(): RouteDeckProjection {
  return useRouteDeckContext().state.projection
}

export function useRouteDeckSurface(name: string): RouteDeckSurface | null {
  return useRouteDeckProjection().surfaces[name] || null
}

export function useRouteDeckOperations(): RouteDeckOperation[] {
  return useRouteDeckProjection().legal_operations
}

export function useRouteDeckOperation(id: string): RouteDeckOperation | null {
  const operations = useRouteDeckOperations()
  return useMemo(() => operations.find((operation) => operation.id === id) || null, [id, operations])
}

export function useRouteDeckDiagnostics(): Record<string, unknown> {
  const state = useRouteDeckContext().state
  return state.diagnostics || state.projection.diagnostics
}

export function useRouteDeckEventStream(): RouteDeckEvent | null {
  return useRouteDeckContext().state.last_event || null
}

export function useRouteDeckStatus() {
  return useRouteDeckContext().state.status
}

export function useRouteDeckPendingOperation(): RouteDeckPendingOperation | null {
  return useRouteDeckContext().state.pending_operation || null
}

export function useRouteDeckSurfaceOpening(): RouteDeckPendingOperation | null {
  const pendingOperation = useRouteDeckPendingOperation()
  return pendingOperation?.status === 'opening_surface' ? pendingOperation : null
}

export function useRouteDeckDispatch(): (input: RouteDeckDispatchInput) => Promise<RouteDeckDispatchResult> {
  return useRouteDeckStore().dispatch
}

export function useRouteDeckInspect(): (input?: RouteDeckInspectInput) => Promise<RouteDeckIntrospection> {
  return useRouteDeckStore().inspect
}

function useRouteDeckContext(): RouteDeckContextValue {
  const context = useContext(RouteDeckContext)
  if (!context) {
    throw new Error('RouteDeck hooks must be used inside RouteDeckProvider')
  }
  return context
}
