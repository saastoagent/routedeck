import {
  RouteDeckNavigationControls,
  useRouteDeckContract,
  useRouteDeckCurrentNode,
} from "@routedeck/react";

export function BuyerNavigation() {
  const contract = useRouteDeckContract();
  const currentNode = useRouteDeckCurrentNode();
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
      <p className="buyer-location" aria-live="polite">
        {currentTitle ?? currentNode}
      </p>
      <RouteDeckNavigationControls className="buyer-history-controls" />
    </header>
  );
}
