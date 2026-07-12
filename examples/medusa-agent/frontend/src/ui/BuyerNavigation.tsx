import { useCallback, useState } from "react";
import {
  RouteDeckError,
  RouteDeckNavigationControls,
  useRouteDeckContract,
  useRouteDeckCurrentNode,
  useRouteDeckDispatch,
  useRouteDeckOperation,
} from "@routedeck/react";

const BROWSE_PRODUCTS = "catalog.list";
const OPEN_CART = "cart.open";

export function BuyerNavigation() {
  const contract = useRouteDeckContract();
  const currentNode = useRouteDeckCurrentNode();
  const browseOperation = useRouteDeckOperation(BROWSE_PRODUCTS);
  const cartOperation = useRouteDeckOperation(OPEN_CART);
  const dispatch = useRouteDeckDispatch();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const run = useCallback(async (operationId: string) => {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await dispatch(operationId);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught
          : new Error("The RouteDeck navigation operation failed."),
      );
    } finally {
      setPending(false);
    }
  }, [dispatch, pending]);
  const browse = useCallback(() => void run(BROWSE_PRODUCTS), [run]);
  const openCart = useCallback(() => void run(OPEN_CART), [run]);
  const currentTitle =
    currentNode === null ? "Starting session" : contract.nodes[currentNode]?.title;

  return (
    <header className="buyer-nav">
      <div className="buyer-brand" aria-label="Medusa Agent home">
        <span className="buyer-brand-mark" aria-hidden="true">M</span>
        <span>
          <strong>Medusa Agent</strong>
          <small>Commerce, supervised by RouteDeck</small>
        </span>
      </div>
      <nav aria-label="Buyer navigation">
        <button
          type="button"
          disabled={pending || browseOperation === null}
          onClick={browse}
        >
          Products
        </button>
        <button
          type="button"
          disabled={pending || cartOperation === null}
          onClick={openCart}
        >
          Cart
        </button>
      </nav>
      {error === null ? null : (
        <RouteDeckError code="buyer_navigation_failed" message={error.message} />
      )}
      <RouteDeckNavigationControls className="buyer-history-controls" />
      <p className="buyer-location" aria-live="polite">
        {currentTitle ?? currentNode}
      </p>
    </header>
  );
}
