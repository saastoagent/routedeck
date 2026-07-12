import {
  createContext,
  useContext,
  useMemo,
  type PropsWithChildren,
} from "react";
import {
  createRouteDeckRequestId,
  type FrontendContract,
  type RouteDeckPrivateFormState,
  type RouteDeckRouteCodec,
  type RouteDeckRouteController,
  type RouteDeckRouteLocation,
  type RouteDeckStore,
} from "@routedeck/core";

import {
  createRouteDeckMutationController,
  type RouteDeckMutationController,
} from "../operations/controller";

export interface RouteDeckNavigationActions {
  back?(): void | Promise<void>;
  forward?(): void | Promise<void>;
  cancel?(): void | Promise<void>;
  open?(location: RouteDeckRouteLocation): void | Promise<void>;
  openPath?(path: string, options?: { replace?: boolean }): void | Promise<void>;
  retryNavigation?(): void | Promise<void>;
  abandonNavigation?(): void | Promise<void>;
}

export interface RouteDeckReactRuntime {
  store: RouteDeckStore;
  contract: FrontendContract;
  routeCodec: RouteDeckRouteCodec | null;
  routeController: RouteDeckRouteController | null;
  privateForms: RouteDeckPrivateFormState | null;
  navigationActions: RouteDeckNavigationActions | null;
  createRequestId: () => string;
  mutationController: RouteDeckMutationController;
}

const RouteDeckContext = createContext<RouteDeckReactRuntime | null>(null);

export interface RouteDeckProviderProps extends PropsWithChildren {
  store: RouteDeckStore;
  contract: FrontendContract;
  routeCodec?: RouteDeckRouteCodec;
  routeController?: RouteDeckRouteController;
  privateForms?: RouteDeckPrivateFormState;
  navigationActions?: RouteDeckNavigationActions;
  createRequestId?: () => string;
}

export function RouteDeckProvider({
  children,
  store,
  contract,
  routeCodec,
  routeController,
  privateForms,
  navigationActions,
  createRequestId = createRouteDeckRequestId,
}: RouteDeckProviderProps) {
  const runtime = useMemo<RouteDeckReactRuntime>(
    () => {
      const mutationController = createRouteDeckMutationController({
        store,
        createRequestId,
      });
      return {
        store,
        contract,
        routeCodec: routeCodec ?? null,
        routeController: routeController ?? null,
        privateForms: privateForms ?? null,
        navigationActions: navigationActions ?? null,
        createRequestId,
        mutationController,
      };
    },
    [
      store,
      contract,
      routeCodec,
      routeController,
      privateForms,
      navigationActions,
      createRequestId,
    ],
  );

  return (
    <RouteDeckContext.Provider value={runtime}>
      {children}
    </RouteDeckContext.Provider>
  );
}

export function useRouteDeckRuntime(): RouteDeckReactRuntime {
  const runtime = useContext(RouteDeckContext);
  if (runtime === null) {
    throw new Error("RouteDeck hooks require a RouteDeckProvider.");
  }
  return runtime;
}
