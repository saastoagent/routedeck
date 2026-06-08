import { useCallback, useEffect, useMemo, useState } from "react";

const SESSION_STORAGE_KEY = "medusa-agent-routedeck-session";

export interface ProductVariant {
  entity_key: string;
  title: string;
  options?: string[];
}

export interface ProductSummary {
  entity_key: string;
  title: string;
  description?: string | null;
  thumbnail?: string | null;
  variants?: ProductVariant[];
}

export interface CartItem {
  entity_key?: string;
  title?: string | null;
  quantity: number;
}

export interface RouteDeckSurfaceEvent {
  surface_id: string;
  affordance_id: string;
  entity_key?: string;
  payload?: Record<string, unknown>;
}

export interface RouteDeckOperation {
  id: string;
  label: string;
  description?: string | null;
  invocation_kind?: "direct" | "form" | "entity_selector" | "surface" | "hidden";
  can_dispatch_now?: boolean;
  missing_args?: string[];
  required_args?: string[];
  capability_id?: string | null;
  surface_id?: string | null;
  target_node?: string | null;
}

export interface RouteDeckCapability {
  capability_id: string;
  label: string;
  operation_ids?: string[];
  entity_kinds?: string[];
  surface_ids?: string[];
  description?: string | null;
}

export interface RouteDeckAvailableEntity {
  kind: string;
  entity_key: string;
  label: string;
  parent_label?: string | null;
  rendered_on?: string[];
  operations?: Array<{ operation_id: string }>;
}

export interface RouteDeckSurfaceAffordance {
  surface_id: string;
  affordance_id: string;
  event: string;
  capability_id?: string | null;
  operation_id?: string | null;
  entity_key?: string | null;
  entity_keys?: string[];
}

export interface RouteDeckDeepLink {
  url: string;
  resumable?: boolean;
  requires_auth?: boolean;
  label?: string | null;
}

export interface RouteDeckNavGraph {
  current?: {
    node_id?: string;
    surface_id?: string | null;
    deeplink?: RouteDeckDeepLink | null;
  };
  nodes?: Array<{
    id: string;
    label: string;
    surface_id?: string | null;
    deeplink?: RouteDeckDeepLink | null;
    capability_ids?: string[];
    metadata?: {
      description?: string;
      allowed_actions?: string[];
    };
  }>;
  edges?: Array<{
    from?: string;
    to?: string;
    action_id?: string | null;
    capability_id?: string | null;
  }>;
  reachable?: string[];
}

export interface RouteDeckProjection {
  graph_node?: string;
  navigation?: {
    current?: {
      node_id?: string;
      surface_id?: string | null;
      deeplink?: RouteDeckDeepLink | null;
    };
  };
  navgraph?: RouteDeckNavGraph | null;
  legal_operations?: RouteDeckOperation[];
  capabilities?: RouteDeckCapability[];
  available_entities?: RouteDeckAvailableEntity[];
  rendered_entities?: RouteDeckAvailableEntity[];
  surface_affordances?: RouteDeckSurfaceAffordance[];
  surfaces?: {
    active?: {
      surface_id?: string;
      variant?: string;
      props?: {
        setup?: {
          ready?: boolean;
        };
        summary?: string;
        products?: ProductSummary[];
        product?: ProductSummary;
        selected_variant_entity_key?: string | null;
        cart?: {
          items?: CartItem[];
        };
      };
    };
  };
}

export interface RouteDeckRuntimeState {
  projection?: RouteDeckProjection;
  status?: string;
}

export interface RouteDeckEvent {
  event_type?: string;
  projection_version?: number | null;
  payload?: {
    projection?: RouteDeckProjection;
    state?: RouteDeckRuntimeState;
    [key: string]: unknown;
  };
}

function getSessionId() {
  const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const next = `session-${crypto.randomUUID()}`;
  window.localStorage.setItem(SESSION_STORAGE_KEY, next);
  return next;
}

export function useRouteDeckProjection() {
  const sessionId = useMemo(getSessionId, []);
  const [projection, setProjection] = useState<RouteDeckProjection | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applyProjection = useCallback((nextProjection: RouteDeckProjection) => {
    setProjection(nextProjection);
    setError(null);
  }, []);

  const refresh = useCallback(async () => {
    const routeParams = routeDeckParamsFromLocation();
    routeParams.set("session_id", sessionId);
    const response = await fetch(`/api/medusa-agent/projection?${routeParams.toString()}`);
    if (!response.ok) {
      throw new Error(`RouteDeck projection failed: ${response.status}`);
    }
    const payload = (await response.json()) as RouteDeckProjection;
    applyProjection(payload);
  }, [applyProjection, sessionId]);

  useEffect(() => {
    let cancelled = false;

    refresh().catch((nextError) => {
      if (!cancelled) {
        setError(nextError instanceof Error ? nextError.message : "Projection failed");
      }
    });

    const onPopState = () => {
      refresh().catch((nextError) => {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Projection failed");
        }
      });
    };
    window.addEventListener("popstate", onPopState);

    return () => {
      cancelled = true;
      window.removeEventListener("popstate", onPopState);
    };
  }, [refresh]);

  useEffect(() => {
    const url = projection?.navigation?.current?.deeplink?.url ?? projection?.navgraph?.current?.deeplink?.url;
    if (!url || !url.startsWith("/")) return;
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (currentUrl !== url) {
      window.history.replaceState(window.history.state, "", url);
    }
  }, [projection]);

  const dispatchSurfaceEvent = useCallback(
    async (surfaceEvent: RouteDeckSurfaceEvent) => {
      const response = await fetch("/api/medusa-agent/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          surface_event: surfaceEvent,
          context: { session_id: sessionId, source: "ui" },
        }),
      });
      if (!response.ok) {
        throw new Error(`RouteDeck action failed: ${response.status}`);
      }
      const payload = (await response.json()) as { state?: { projection?: RouteDeckProjection } };
      if (payload.state?.projection) {
        applyProjection(payload.state.projection);
      } else {
        await refresh();
      }
    },
    [applyProjection, refresh, sessionId],
  );

  const dispatchOperation = useCallback(
    async (operationId: string, args: Record<string, unknown> = {}) => {
      const response = await fetch("/api/medusa-agent/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          operation_id: operationId,
          args,
          context: { session_id: sessionId, source: "ui" },
        }),
      });
      if (!response.ok) {
        throw new Error(`RouteDeck action failed: ${response.status}`);
      }
      const payload = (await response.json()) as { state?: { projection?: RouteDeckProjection } };
      if (payload.state?.projection) {
        applyProjection(payload.state.projection);
      } else {
        await refresh();
      }
    },
    [applyProjection, refresh, sessionId],
  );

  const applyRouteDeckEvent = useCallback(
    (event: RouteDeckEvent) => {
      const nextProjection = event.payload?.state?.projection ?? event.payload?.projection;
      if (nextProjection) {
        applyProjection(nextProjection);
      }
    },
    [applyProjection],
  );

  return { projection, error, dispatchSurfaceEvent, dispatchOperation, applyRouteDeckEvent, sessionId };
}

function routeDeckParamsFromLocation() {
  const routeDeckParams = new URLSearchParams();
  const pathSegments = window.location.pathname
    .split("/")
    .filter(Boolean)
    .map(safeDecodePathSegment);

  const pathNode = pathSegments[0];
  if (pathNode === "home") {
    routeDeckParams.set("rd_node", "home");
  } else if (pathNode === "browse") {
    routeDeckParams.set("rd_node", "browse");
  } else if (pathNode === "cart") {
    routeDeckParams.set("rd_node", "cart");
  } else if (pathNode === "detail") {
    routeDeckParams.set("rd_node", "detail");
    if (pathSegments[1] === "entity" && pathSegments[2]) {
      routeDeckParams.set("rd_entity", pathSegments[2]);
    } else if (pathSegments[1]) {
      routeDeckParams.set("rd_product", pathSegments[1]);
    }
  }

  const legacyParams = new URLSearchParams(window.location.search);
  if (!routeDeckParams.has("rd_node")) {
    for (const key of ["rd_node", "rd_product", "rd_entity"]) {
      const value = legacyParams.get(key);
      if (value) routeDeckParams.set(key, value);
    }
  }
  if (!routeDeckParams.has("rd_node")) {
    routeDeckParams.set("rd_node", "home");
  }
  return routeDeckParams;
}

function safeDecodePathSegment(segment: string) {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}
