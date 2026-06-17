import { useEffect, useState } from "react";

export type RouteNodeId = "home" | "browse" | "detail" | "cart";

export interface RouteDeckProjection {
  graph_node: RouteNodeId | string;
  legal_operations: unknown[];
  surfaces: {
    active?: RouteDeckSurface;
  };
  presentation_state: {
    active_surface_id?: string;
    chat_suggestions?: RouteDeckChatSuggestion[];
    [key: string]: unknown;
  };
  navigation: {
    current: RouteDeckLocation;
  };
  navgraph?: {
    current: RouteDeckLocation;
    nodes: RouteDeckNavGraphNode[];
    edges: RouteDeckNavGraphEdge[];
    traversed: string[];
    reachable: string[];
  };
  available_entities: RouteDeckAvailableEntity[];
  surface_affordances: unknown[];
}

export interface ProjectionUpdatePayload {
  source?: string;
  intent?: string;
  reason?: string;
  route_context?: {
    path?: string;
    surface_id?: string;
  };
  surface_intent?: {
    surface_id?: string;
  };
  payload?: {
    projection?: unknown;
    state?: {
      projection?: unknown;
    };
  };
  projection_version?: number;
  projection?: unknown;
}

export interface RouteDeckSurface {
  name: string;
  surface_id?: string | null;
  component: string;
  variant?: string;
  role?: string;
  surface_kind?: string;
  label?: string | null;
  props?: Record<string, unknown>;
}

export interface RouteDeckChatSuggestion {
  label: string;
  message: string;
}

export interface RouteDeckLocation {
  node_id: string;
  surface_id?: string | null;
  params?: Record<string, unknown>;
  deeplink?: {
    url: string;
    label?: string | null;
  } | null;
}

export interface RouteDeckNavGraphNode {
  id: string;
  label: string;
  surface_id?: string | null;
  deeplink?: {
    url: string;
    label?: string | null;
  } | null;
}

export interface RouteDeckNavGraphEdge {
  from?: string;
  to?: string;
  source?: string;
  target?: string;
}

export interface RouteDeckAvailableEntity {
  kind: string;
  entity_key: string;
  label: string;
  rendered_on?: string[];
  metadata?: Record<string, unknown>;
}

export function useRouteDeckProjection() {
  const [projection, setProjection] = useState<RouteDeckProjection | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadProjection() {
      try {
        const response = await fetch(projectionEndpointFromLocation());
        if (!response.ok) {
          throw new Error(`Projection request failed: ${response.status}`);
        }
        const nextProjection = (await response.json()) as RouteDeckProjection;
        if (!cancelled) {
          setProjection(nextProjection);
          setError(null);
        }
      } catch (projectionError) {
        if (!cancelled) {
          setError(projectionError instanceof Error ? projectionError.message : "Projection request failed.");
        }
      }
    }

    loadProjection();

    return () => {
      cancelled = true;
    };
  }, []);

  const applyProjectionUpdate = (update: ProjectionUpdatePayload) => {
    const nextProjection = projectionFromUpdate(update);
    if (!isRenderableProjection(nextProjection)) return;

    setProjection(nextProjection);
    setError(null);
    updateBrowserLocation(update, nextProjection);
  };

  return { projection, error, applyProjectionUpdate };
}

function projectionEndpointFromLocation(): string {
  if (typeof window === "undefined") {
    return "/api/medusa-agent/projection?path=%2F";
  }

  const params = new URLSearchParams();
  params.set("path", window.location.pathname || "/");

  const surfaceId = new URLSearchParams(window.location.search).get("surface_id");
  if (surfaceId) {
    params.set("surface_id", surfaceId);
  }

  return `/api/medusa-agent/projection?${params.toString()}`;
}

function projectionFromUpdate(update: ProjectionUpdatePayload): unknown {
  return update.projection || update.payload?.projection || update.payload?.state?.projection;
}

function isRenderableProjection(value: unknown): value is RouteDeckProjection {
  if (!isRecord(value)) return false;

  return (
    typeof value.graph_node === "string" &&
    Array.isArray(value.legal_operations) &&
    isRecord(value.surfaces) &&
    isRecord(value.presentation_state) &&
    isRecord(value.navigation) &&
    isRecord(value.navigation.current) &&
    Array.isArray(value.available_entities) &&
    Array.isArray(value.surface_affordances)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function updateBrowserLocation(update: ProjectionUpdatePayload, projection: RouteDeckProjection) {
  if (typeof window === "undefined") return;

  const path =
    update.route_context?.path ||
    pathOnly(projection.navigation?.current?.deeplink?.url || "") ||
    "/";
  const surfaceId =
    update.route_context?.surface_id ||
    update.surface_intent?.surface_id ||
    projection.navigation?.current?.surface_id ||
    "";
  const currentPath = window.location.pathname || "/";
  const currentSurfaceId = new URLSearchParams(window.location.search).get("surface_id") || "";

  if (path === currentPath && surfaceId === currentSurfaceId) return;

  const nextUrl = surfaceId ? `${path}?surface_id=${encodeURIComponent(surfaceId)}` : path;
  window.history.pushState({}, "", nextUrl);
}

function pathOnly(url: string): string {
  return url.split("?", 1)[0] || "";
}
