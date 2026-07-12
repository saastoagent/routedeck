import { RouteDeckProvider } from "@routedeck/react";

import { medusaRouteDeckSurfaces } from "../routedeck/surfaces";
import { AgentShell } from "../ui/AgentShell";
import { BuyerNavigation } from "../ui/BuyerNavigation";
import { RouteDeckStatusRail } from "../ui/RouteDeckStatusRail";
import type { MedusaRouteDeck } from "./createRouteDeck";
import type { AgentChatClient, AgentHistoryTurn } from "./chatClient";

export interface AppProps {
  routeDeck: MedusaRouteDeck;
  chatClient?: AgentChatClient;
  initialConversation?: readonly AgentHistoryTurn[];
}

export function App({
  routeDeck,
  chatClient,
  initialConversation = [],
}: AppProps) {
  return (
    <RouteDeckProvider
      store={routeDeck.store}
      contract={routeDeck.contract}
      routeCodec={routeDeck.routes}
      routeController={routeDeck.routeController}
      privateForms={routeDeck.privateForms}
      navigationActions={routeDeck.navigationActions}
    >
      <div className="buyer-app" data-testid="medusa-buyer-app">
        <BuyerNavigation />
        <div className="buyer-workspace">
          <AgentShell
            registry={medusaRouteDeckSurfaces}
            initialConversation={initialConversation}
            {...(chatClient === undefined ? {} : { client: chatClient })}
          />
          <RouteDeckStatusRail />
        </div>
      </div>
    </RouteDeckProvider>
  );
}
