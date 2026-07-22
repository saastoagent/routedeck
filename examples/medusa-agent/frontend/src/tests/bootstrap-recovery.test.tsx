import "@testing-library/jest-dom/vitest";

import { useEffect } from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  createRouteDeckRouteCodec,
  createRouteDeckStore,
  RouteDeckHttpError,
  RouteDeckOutcomeUnknownError,
  RouteDeckStreamError,
} from "@routedeck/core";
import { RouteDeckBootstrapBoundary } from "@routedeck/react";
import {
  MemoryHistoryHarness,
  routeDeckFrontendContractFixture,
  routeDeckProjectionFixture,
  ScriptedRouteDeckClient,
} from "@routedeck/testing";
import { afterEach, expect, it, vi } from "vitest";

import { BootstrapRecoveryShell } from "../app/BootstrapRecoveryShell";
import { BootstrapLoadingShell } from "../app/BootstrapLoadingShell";

afterEach(cleanup);

it("retries the retained session create and keeps new-session creation distinct", async () => {
  const client = new ScriptedRouteDeckClient();
  const requests: Parameters<typeof client.createSession>[0][] = [];
  vi.spyOn(client, "createSession").mockImplementation(async (request) => {
    requests.push(request);
    if (requests.length === 1) {
      throw new RouteDeckOutcomeUnknownError(
        request.request_id,
        "Session creation response was lost.",
      );
    }
    return routeDeckProjectionFixture();
  });
  let requestSequence = 0;
  const store = createRouteDeckStore({
    client,
    bootstrapMode: "create",
    createRequestId: () => `session-create-${++requestSequence}`,
  });
  await expect(store.bootstrap()).rejects.toBeInstanceOf(
    RouteDeckOutcomeUnknownError,
  );
  const onReady = vi.fn();

  renderRecoveryBoundary(store, onReady);

  expect(
    screen.getByRole("button", { name: "Retry creating this buyer session" }),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Start a new buyer session" }),
  ).toBeVisible();
  expect(document.body).not.toHaveTextContent("session-create-1");
  expect(JSON.stringify(store.getState().pendingBootstrap)).not.toContain(
    "session-create-1",
  );

  fireEvent.click(
    screen.getByRole("button", { name: "Retry creating this buyer session" }),
  );

  await waitFor(() => expect(onReady).toHaveBeenCalledOnce());
  expect(requests[1]).toBe(requests[0]);
  expect(store.getState().syncStatus).toBe("live");
  store.dispose();
});

it("reconnects the current session after an initial stream failure", async () => {
  const { store } = await initialStreamFailureHarness();
  const resync = vi.spyOn(store, "resync");
  const onReady = vi.fn();
  await expect(store.startNewSession()).rejects.toMatchObject({
    code: "new_session_recovery_unavailable",
  });
  renderRecoveryBoundary(store, onReady);

  expect(
    screen.getByRole("button", { name: "Reconnect current buyer session" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Start a new buyer session" }),
  ).not.toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", { name: "Reconnect current buyer session" }),
  );

  await waitFor(() => expect(resync).toHaveBeenCalledOnce());
  await waitFor(() => expect(onReady).toHaveBeenCalledOnce());
  expect(store.getState().syncStatus).toBe("live");
  store.dispose();
});

it("opens the App when background recovery makes the subscribed store live", async () => {
  const { store } = await initialStreamFailureHarness();
  const onReady = vi.fn();
  renderRecoveryBoundary(store, onReady);

  await act(async () => store.resync());

  await waitFor(() => expect(onReady).toHaveBeenCalledOnce());
  store.dispose();
});

it("offers retry and abandon actions for initial navigation recovery", async () => {
  const client = new ScriptedRouteDeckClient();
  const home = routeDeckProjectionFixture({
    nodeId: "home",
    routeTemplate: "/",
    historyEntryId: 1,
  });
  const product = routeDeckProjectionFixture({
    nodeId: "detail",
    routeTemplate: "/items/{item_handle}",
    routeParams: [{ name: "item_handle", value: "item-public" }],
    sessionVersion: 2,
    projectionVersion: 2,
    eventCursor: 1,
    historyEntryId: 2,
  });
  client.enqueueSession(home);
  client.enqueueSession(product);
  vi.spyOn(client, "navigate").mockImplementation(async (request) => {
    throw new RouteDeckOutcomeUnknownError(
      request.request_id,
      "Initial navigation response was lost.",
    );
  });
  const history = new MemoryHistoryHarness("/items/item-public");
  const routes = createRouteDeckRouteCodec(routeDeckFrontendContractFixture(), {
    validatePublicRouteKey: (_name, value) => value === "item-public",
    validateResumeCapability: () => false,
  });
  const store = createRouteDeckStore({
    client,
    history,
    routes,
    bootstrapMode: "resume",
    createRequestId: () => "initial-navigation-1",
  });
  await expect(store.bootstrap()).rejects.toBeInstanceOf(
    RouteDeckOutcomeUnknownError,
  );
  const onReady = vi.fn();

  renderRecoveryBoundary(store, onReady);

  expect(
    screen.getByRole("button", { name: "Retry opening this route" }),
  ).toBeVisible();
  expect(
    screen.getByRole("button", {
      name: "Abandon route and use current session",
    }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Start a new buyer session" }),
  ).not.toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Abandon route and use current session",
    }),
  );

  await waitFor(() => expect(onReady).toHaveBeenCalledOnce());
  expect(store.getState().syncStatus).toBe("live");
  expect(client.calls).toContain("events.connect:1");
  store.dispose();
});

it("requires an explicit new-session action after resume expiry", async () => {
  const client = new ScriptedRouteDeckClient();
  vi.spyOn(client, "getSession").mockRejectedValue(
    new RouteDeckHttpError(410, null, "The buyer session expired."),
  );
  client.enqueueCreatedSession(routeDeckProjectionFixture());
  const store = createRouteDeckStore({
    client,
    bootstrapMode: "resume",
    createRequestId: () => "replacement-session-1",
  });
  await expect(store.bootstrap()).rejects.toMatchObject({ status: 410 });
  const onReady = vi.fn();

  renderRecoveryBoundary(store, onReady);

  expect(
    screen.getByRole("heading", { name: "Buyer session expired" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", {
      name: "Retry creating this buyer session",
    }),
  ).not.toBeInTheDocument();
  expect(client.sessionCreateRequests).toHaveLength(0);

  fireEvent.click(
    screen.getByRole("button", { name: "Start a new buyer session" }),
  );

  await waitFor(() => expect(onReady).toHaveBeenCalledOnce());
  expect(client.sessionCreateRequests).toEqual([
    { request_id: "replacement-session-1" },
  ]);
  store.dispose();
});

it("requires an explicit new session for a missing no-cookie session-bound link", async () => {
  const client = new ScriptedRouteDeckClient();
  vi.spyOn(client, "getSession").mockRejectedValue(
    new RouteDeckHttpError(
      404,
      {
        code: "session_not_found",
        correlation_id: "correlation-missing-session",
        kind: "persistence",
        phase: "session_lookup",
        public_message: "The buyer session was not found.",
      },
      "The buyer session was not found.",
    ),
  );
  client.enqueueCreatedSession(routeDeckProjectionFixture());
  const history = new MemoryHistoryHarness(
    "/secure?resume_handle=resume-missing",
  );
  const routes = createRouteDeckRouteCodec(routeDeckFrontendContractFixture(), {
    validateResumeCapability: () => false,
  });
  const store = createRouteDeckStore({
    client,
    history,
    routes,
    bootstrapMode: "resume_or_create_shareable",
    createRequestId: () => "replacement-missing-session-1",
  });
  await expect(store.bootstrap()).rejects.toMatchObject({ status: 404 });
  const onReady = vi.fn();

  renderRecoveryBoundary(store, onReady);

  expect(
    screen.getByRole("heading", { name: "Buyer session unavailable" }),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Start a new buyer session" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Reconnect current buyer session" }),
  ).not.toBeInTheDocument();
  expect(screen.getAllByRole("button")).toHaveLength(1);
  expect(client.sessionCreateRequests).toHaveLength(0);

  fireEvent.click(
    screen.getByRole("button", { name: "Start a new buyer session" }),
  );

  await waitFor(() => expect(onReady).toHaveBeenCalledOnce());
  expect(client.sessionCreateRequests).toEqual([
    { request_id: "replacement-missing-session-1" },
  ]);
  store.dispose();
});

async function initialStreamFailureHarness() {
  const client = new ScriptedRouteDeckClient();
  const initial = routeDeckProjectionFixture({
    sessionVersion: 1,
    projectionVersion: 1,
    eventCursor: 0,
  });
  client.enqueueSession(initial);
  client.enqueueSession({
    ...initial,
    session_version: 2,
    projection_version: 2,
    event_cursor: 1,
  });
  let streamCall = 0;
  vi.spyOn(client, "connectEvents").mockImplementation((options) => {
    streamCall += 1;
    if (streamCall === 1) {
      options.onError?.(
        new RouteDeckStreamError(
          "stream_failed",
          "Initial stream connection failed.",
        ),
      );
    } else {
      options.onOpen?.({ after: options.after, reconnecting: false });
    }
    return {
      close: vi.fn(),
      done: new Promise<void>(() => undefined),
    };
  });
  const store = createRouteDeckStore({ client, bootstrapMode: "resume" });
  await store.bootstrap().then(
    () => {
      throw new Error("Expected initial stream bootstrap to fail.");
    },
    () => undefined,
  );
  return { client, store };
}

function renderRecoveryBoundary(
  store: ReturnType<typeof createRouteDeckStore>,
  onReady: () => void,
) {
  function Ready() {
    useEffect(onReady, []);
    return null;
  }
  return render(
    <RouteDeckBootstrapBoundary
      store={store}
      loading={<BootstrapLoadingShell />}
      recovery={(state) => <BootstrapRecoveryShell state={state} />}
    >
      <Ready />
    </RouteDeckBootstrapBoundary>,
  );
}
