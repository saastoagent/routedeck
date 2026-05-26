import type { RouteDeckProjection, RouteDeckSurface } from './types'

export function resolveRouteDeckActiveSurface(projection: RouteDeckProjection): RouteDeckSurface | null {
  const currentSurfaceId = projection.navigation?.current?.surface_id
  if (currentSurfaceId) {
    const current = Object.values(projection.surfaces).find((surface) => surface.surface_id === currentSurfaceId)
    if (current) return current
  }
  return Object.values(projection.surfaces).find((surface) => surface.role === 'active') || null
}
