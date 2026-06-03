import { useCallback, useEffect, useMemo, useState } from "react";

const SESSION_STORAGE_KEY = "medusa-agent-routedeck-session";

export interface ProductVariant {
  variant_ref: string;
  title: string;
  options?: string[];
}

export interface ProductSummary {
  product_ref: string;
  title: string;
  description?: string | null;
  thumbnail?: string | null;
  variants?: ProductVariant[];
}

export interface CartItem {
  line_ref?: string;
  title?: string | null;
  quantity: number;
}

export interface RouteDeckProjection {
  graph_node?: string;
  legal_operations?: Array<{ id: string; label: string }>;
  surfaces?: {
    active?: {
      variant?: string;
      props?: {
        setup?: {
          ready?: boolean;
        };
        products?: ProductSummary[];
        product?: ProductSummary;
        selected_variant_ref?: string | null;
        cart?: {
          cart_ref?: string | null;
          items?: CartItem[];
        };
      };
    };
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

  const refresh = useCallback(async () => {
    const response = await fetch(`/api/routedeck/projection?session_id=${encodeURIComponent(sessionId)}`);
    if (!response.ok) {
      throw new Error(`RouteDeck projection failed: ${response.status}`);
    }
    const payload = (await response.json()) as RouteDeckProjection;
    setProjection(payload);
    setError(null);
  }, [sessionId]);

  useEffect(() => {
    let cancelled = false;

    refresh().catch((nextError) => {
      if (!cancelled) {
        setError(nextError instanceof Error ? nextError.message : "Projection failed");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [refresh]);

  const dispatch = useCallback(
    async (operationId: string, args: Record<string, unknown> = {}) => {
      const response = await fetch("/api/routedeck/dispatch", {
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
      await refresh();
    },
    [refresh, sessionId],
  );

  return { projection, error, dispatch };
}
