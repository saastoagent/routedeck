import {
  render,
  type RenderOptions,
  type RenderResult,
} from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import {
  createPrivateFormState,
  createRouteDeckRouteCodec,
  createRouteDeckRouteController,
  createRouteDeckStore,
  type FrontendContract,
  type RouteDeckProjection,
} from "@routedeck/core";
import {
  RouteDeckProvider,
  type RouteDeckNavigationActions,
} from "@routedeck/react";

import { MemoryHistoryHarness, ScriptedRouteDeckClient } from "./storeHarness";

export interface RouteDeckComponentHarnessOptions {
  projection: RouteDeckProjection;
  contract: FrontendContract;
  client?: ScriptedRouteDeckClient;
  history?: MemoryHistoryHarness;
  navigationActions?: RouteDeckNavigationActions;
  validatePublicRouteKey?: (name: string, value: string) => boolean;
  validateResumeCapability?: (
    handle: string,
    nodeId: string,
    params: Readonly<Record<string, string>>,
  ) => boolean;
  renderOptions?: Omit<RenderOptions, "wrapper">;
}

export interface RouteDeckComponentHarness extends RenderResult {
  client: ScriptedRouteDeckClient;
  history: MemoryHistoryHarness;
  routes: ReturnType<typeof createRouteDeckRouteCodec>;
  routeController: ReturnType<typeof createRouteDeckRouteController>;
  store: ReturnType<typeof createRouteDeckStore>;
  privateForms: ReturnType<typeof createPrivateFormState>;
  dispose(): void;
}

export async function renderRouteDeckComponent(
  ui: ReactElement,
  options: RouteDeckComponentHarnessOptions,
): Promise<RouteDeckComponentHarness> {
  const client = options.client ?? new ScriptedRouteDeckClient();
  const routes = createRouteDeckRouteCodec(options.contract, {
    validatePublicRouteKey:
      options.validatePublicRouteKey ?? (() => true),
    validateResumeCapability:
      options.validateResumeCapability ?? (() => true),
  });
  const history =
    options.history ??
    new MemoryHistoryHarness(projectionPath(routes, options.projection));
  const routeController = createRouteDeckRouteController({
    codec: routes,
    history,
    context: () => ({ sessionAvailable: true }),
  });
  client.enqueueSession(options.projection);
  let requestSequence = 0;
  const store = createRouteDeckStore({
    client,
    history,
    routes,
    routeController,
    bootstrapMode: "resume",
    createRequestId: () => `component-request-${++requestSequence}`,
  });
  const privateForms = createPrivateFormState(client.privateForms);
  await store.bootstrap();
  const navigationActions = {
    back: store.back,
    forward: store.forward,
    cancel: store.cancel,
    openPath: store.openPath,
    retryNavigation: store.retryNavigation,
    abandonNavigation: store.abandonNavigation,
    ...options.navigationActions,
  };

  const result = render(ui, {
    ...options.renderOptions,
    wrapper: ({ children }: { children: ReactNode }) => (
      <RouteDeckProvider
        store={store}
        contract={options.contract}
        routeCodec={routes}
        routeController={routeController}
        privateForms={privateForms}
        navigationActions={navigationActions}
        createRequestId={() => `component-request-${++requestSequence}`}
      >
        {children}
      </RouteDeckProvider>
    ),
  });

  return {
    ...result,
    client,
    history,
    routes,
    routeController,
    store,
    privateForms,
    dispose() {
      result.unmount();
      privateForms.dispose();
      store.dispose();
    },
  };
}

function projectionPath(
  routes: ReturnType<typeof createRouteDeckRouteCodec>,
  projection: RouteDeckProjection,
): string {
  const params = Object.fromEntries(
    projection.current.route_params.map((parameter) => {
      if (typeof parameter.value !== "string") {
        throw new TypeError(`Route parameter ${parameter.name} must be a string.`);
      }
      return [parameter.name, parameter.value];
    }),
  );
  const resumeHandle = projection.navigation.resume_handle;
  return routes.encode(projection.current.node_id, params, {
    ...(resumeHandle === null ? {} : { resumeHandle }),
  });
}
