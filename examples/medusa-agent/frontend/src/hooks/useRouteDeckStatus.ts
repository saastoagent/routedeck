import { useEffect, useState } from "react";

export interface RouteDeckProjection {
  surfaces?: {
    active?: {
      props?: {
        setup?: {
          ready?: boolean;
        };
      };
    };
  };
}

export function useRouteDeckStatus() {
  const [projection, setProjection] = useState<RouteDeckProjection | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetch("/api/medusa-agent/projection")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`RouteDeck status failed: ${response.status}`);
        }
        return response.json() as Promise<RouteDeckProjection>;
      })
      .then((payload) => {
        if (!cancelled) {
          setProjection(payload);
        }
      })
      .catch((nextError) => {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Status failed");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { projection, error };
}
