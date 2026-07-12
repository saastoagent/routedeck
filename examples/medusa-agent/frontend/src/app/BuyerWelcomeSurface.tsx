import { useCallback, useState } from "react";
import {
  RouteDeckError,
  type RouteDeckSurfaceComponentProps,
} from "@routedeck/react";

export function BuyerWelcomeSurface({
  dispatchAffordance,
}: RouteDeckSurfaceComponentProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const browse = useCallback(async () => {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await dispatchAffordance("browse_products");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught
          : new Error("RouteDeck could not open the catalog."),
      );
    } finally {
      setPending(false);
    }
  }, [dispatchAffordance, pending]);
  return (
    <section>
      <h1>Shop with Medusa</h1>
      <p>Ask the buyer agent for help or browse the available products.</p>
      {error === null ? null : (
        <RouteDeckError code="catalog_browse_failed" message={error.message} />
      )}
      <button
        type="button"
        disabled={pending}
        onClick={() => void browse()}
      >
        {pending ? "Opening products…" : "Browse products"}
      </button>
    </section>
  );
}
