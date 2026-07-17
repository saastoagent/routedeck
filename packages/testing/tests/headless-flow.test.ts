import {
  createPrivateFormState,
  createRouteDeckRouteCodec,
  createRouteDeckRouteController,
  createRouteDeckStore,
  RouteDeckHttpError,
  RouteDeckOutcomeUnknownError,
  RouteDeckStreamError,
} from "@routedeck/core";
import { describe, expect, it, vi } from "vitest";

import {
  flushRouteDeckTasks,
  MemoryHistoryHarness,
  routeDeckDispatchResultFixture,
  routeDeckEventFixture,
  routeDeckFrontendContractFixture,
  routeDeckProjectionFixture,
  ScriptedRouteDeckClient,
} from "../src/index";

describe("headless RouteDeck flow", () => {
  it("resyncs authoritatively before returning live after an SSE reconnect", async () => {
    const client = new ScriptedRouteDeckClient();
    client.enqueueSession(
      routeDeckProjectionFixture({
        nodeId: "home",
        routeTemplate: "/",
        sessionVersion: 1,
        projectionVersion: 1,
        eventCursor: 0,
      }),
    );
    client.enqueueSession(
      routeDeckProjectionFixture({
        nodeId: "home",
        routeTemplate: "/",
        sessionVersion: 3,
        projectionVersion: 2,
        eventCursor: 4,
      }),
    );
    const store = createRouteDeckStore({ client, bootstrapMode: "resume" });
    await store.bootstrap();
    expect(store.getState().syncStatus).toBe("live");

    client.failStream(
      new RouteDeckStreamError("stream_failed", "Connection lost."),
    );
    expect(store.getState().syncStatus).toBe("error");

    client.reopenStream();
    expect(store.getState().syncStatus).toBe("resync_required");
    await flushRouteDeckTasks();

    expect(store.getState().syncStatus).toBe("live");
    expect(store.getState().sessionVersion).toBe(3);
    expect(store.getState().projectionVersion).toBe(2);
    expect(client.calls.filter((call) => call === "session.get")).toHaveLength(2);
    expect(client.calls).toContain("events.connect:4");
    store.dispose();
  });

  it("retains an outcome-unknown navigation for explicit exact replay", async () => {
    const client = new ScriptedRouteDeckClient();
    const home = routeDeckProjectionFixture({
      nodeId: "home",
      routeTemplate: "/",
      sessionVersion: 1,
      projectionVersion: 1,
      historyEntryId: 1,
    });
    const product = routeDeckProjectionFixture({
      nodeId: "detail",
      routeTemplate: "/items/{item_handle}",
      routeParams: [{ name: "item_handle", value: "item-public" }],
      sessionVersion: 2,
      projectionVersion: 2,
      historyEntryId: 2,
    });
    client.enqueueSession(home);
    const requests: typeof client.navigationRequests = [];
    let attempt = 0;
    vi.spyOn(client, "navigate").mockImplementation(async (request) => {
      requests.push(request);
      attempt += 1;
      if (attempt === 1) {
        throw new RouteDeckOutcomeUnknownError(
          request.request_id,
          "Navigation response was lost.",
        );
      }
      return product;
    });
    const history = new MemoryHistoryHarness("/");
    const routes = createRouteDeckRouteCodec(
      routeDeckFrontendContractFixture(),
      {
        validatePublicRouteKey: (_name, value) => value === "item-public",
        validateResumeCapability: () => false,
      },
    );
    let requestSequence = 0;
    const store = createRouteDeckStore({
      client,
      history,
      routes,
      bootstrapMode: "resume",
      createRequestId: () => `navigation-${++requestSequence}`,
    });
    await store.bootstrap();

    await expect(store.openPath("/items/item-public")).rejects.toBeInstanceOf(
      RouteDeckOutcomeUnknownError,
    );
    expect(store.getState().pendingNavigation).toMatchObject({
      requestId: "navigation-1",
      intent: { kind: "open_path", path: "/items/item-public" },
    });
    await expect(store.cancel()).rejects.toMatchObject({
      code: "navigation_retry_required",
    });

    await store.retryNavigation();
    expect(requests).toHaveLength(2);
    expect(requests[1]).toBe(requests[0]);
    expect(store.getState().pendingNavigation).toBeNull();
    expect(history.current()).toBe("/items/item-public");
    store.dispose();
  });

  it("bootstraps, applies events and history, keeps forms in memory, and resyncs gaps", async () => {
    const client = new ScriptedRouteDeckClient();
    client.enqueueSession(
      routeDeckProjectionFixture({
        nodeId: "home",
        routeTemplate: "/",
        sessionVersion: 1,
        projectionVersion: 1,
        eventCursor: 0,
      }),
    );
    client.enqueueSession(
      routeDeckProjectionFixture({
        nodeId: "detail",
        routeTemplate: "/items/{item_handle}",
        routeParams: [{ name: "item_handle", value: "item-public" }],
        sessionVersion: 4,
        projectionVersion: 2,
        eventCursor: 3,
      }),
    );
    const history = new MemoryHistoryHarness("/");
    const routes = createRouteDeckRouteCodec(
      routeDeckFrontendContractFixture(),
      {
        validatePublicRouteKey: (_name, value) => value === "item-public",
        validateResumeCapability: (handle) => handle === "resume-public",
      },
    );
    const routeController = createRouteDeckRouteController({
      codec: routes,
      history,
      context: () => ({
        sessionAvailable: true,
        validateResumeCapability: (handle) => handle === "resume-public",
      }),
    });
    const store = createRouteDeckStore({
      client,
      routeController,
      bootstrapMode: "resume",
    });

    await store.bootstrap();
    expect(store.getState().projection?.current.node_id).toBe("home");
    expect(store.getState().syncStatus).toBe("live");
    expect(history.current()).toBe("/");

    client.emit(
      routeDeckEventFixture({
        cursor: 1,
        sessionVersion: 2,
        projectionVersion: 1,
      }),
    );
    expect(store.getState().eventCursor).toBe(1);
    expect(store.getState().syncStatus).toBe("live");

    routeController.navigate(
      "detail",
      { item_handle: "item-public" },
      { historyEntryId: 2 },
    );
    expect(history.current()).toBe("/items/item-public");

    const privateForms = createPrivateFormState(client.privateForms);
    const privateForm = await privateForms.save("contact", {
      request_id: "private-request-1",
      expected_session_version: 2,
      value: { email: "buyer@example.test" },
    });
    expect(privateForm.value).toEqual({ email: "buyer@example.test" });
    expect(store.getState().projection).not.toContain("buyer@example.test");
    expect(client.calls).toContain("private.save:contact");

    client.emit(
      routeDeckEventFixture({
        cursor: 3,
        sessionVersion: 4,
        projectionVersion: 2,
      }),
    );
    expect(store.getState().syncStatus).toBe("resync_required");
    await flushRouteDeckTasks();
    expect(store.getState().syncStatus).toBe("live");
    expect(store.getState().eventCursor).toBe(3);
    expect(store.getState().projection?.current.node_id).toBe("detail");
    expect(history.current()).toBe("/items/item-public");
    expect(client.calls.filter((call) => call === "session.get")).toHaveLength(2);
    expect(client.calls.some((call) => call.includes("/store/"))).toBe(false);

    privateForms.dispose();
    store.dispose();
  });

  it("reconciles a fresh deep link and restores exact browser history entries", async () => {
    const client = new ScriptedRouteDeckClient();
    const home = routeDeckProjectionFixture({
      nodeId: "home",
      routeTemplate: "/",
      sessionVersion: 1,
      projectionVersion: 1,
      historyEntryId: 1,
    });
    const product = routeDeckProjectionFixture({
      nodeId: "detail",
      routeTemplate: "/items/{item_handle}",
      routeParams: [{ name: "item_handle", value: "item-public" }],
      sessionVersion: 2,
      projectionVersion: 2,
      historyEntryId: 2,
    });
    const returnedHome = routeDeckProjectionFixture({
      nodeId: "home",
      routeTemplate: "/",
      sessionVersion: 3,
      projectionVersion: 3,
      historyEntryId: 1,
    });
    client.enqueueSession(home);
    client.enqueueNavigation(product);
    client.enqueueNavigation(returnedHome);
    client.enqueueNavigation({
      ...product,
      session_version: 4,
      projection_version: 4,
    });

    const history = new MemoryHistoryHarness("/items/item-public");
    const routes = createRouteDeckRouteCodec(routeDeckFrontendContractFixture(), {
      validatePublicRouteKey: (_name, value) => value === "item-public",
      validateResumeCapability: () => false,
    });
    let requestId = 0;
    const store = createRouteDeckStore({
      client,
      history,
      routes,
      bootstrapMode: "resume",
      createRequestId: () => `navigation-${++requestId}`,
    });

    await store.bootstrap();
    expect(history.current()).toBe("/items/item-public");
    expect(history.currentEntryId()).toBe(2);
    expect(history.entries).toEqual(["/", "/items/item-public"]);
    expect(history.entryIds).toEqual([1, 2]);
    expect(client.navigationRequests[0]?.intent).toEqual({
      kind: "open_path",
      path: "/items/item-public",
    });

    store.back();
    await flushRouteDeckTasks();
    expect(history.current()).toBe("/");
    expect(history.currentEntryId()).toBe(1);
    expect(store.getState().projection?.current.node_id).toBe("home");
    expect(client.navigationRequests[1]?.intent).toEqual({
      kind: "restore_history_entry",
      history_entry_id: 1,
      path: "/",
    });

    store.forward();
    await flushRouteDeckTasks();
    expect(store.getState().projection?.current.node_id).toBe("detail");
    expect(client.navigationRequests[2]?.intent).toEqual({
      kind: "restore_history_entry",
      history_entry_id: 2,
      path: "/items/item-public",
    });
    store.dispose();
  });

  it("keeps the prior browser entry when SSE advances before dispatch returns", async () => {
    const client = new ScriptedRouteDeckClient();
    const contract = routeDeckFrontendContractFixture();
    contract.nodes.cart = {
      id: "cart",
      title: "Cart",
      route_template: "/cart",
      deep_link_policy: "shareable",
      surfaces: { ...contract.nodes.home!.surfaces },
      operation_ids: [],
    };
    const product = routeDeckProjectionFixture({
      nodeId: "detail",
      routeTemplate: "/items/{item_handle}",
      routeParams: [{ name: "item_handle", value: "item-public" }],
      sessionVersion: 2,
      projectionVersion: 2,
      eventCursor: 1,
      historyEntryId: 2,
    });
    const cart = routeDeckProjectionFixture({
      nodeId: "cart",
      routeTemplate: "/cart",
      sessionVersion: 3,
      projectionVersion: 3,
      eventCursor: 2,
      historyEntryId: 3,
    });
    cart.navigation.can_back = true;
    cart.navigation.can_cancel = true;
    cart.navigation.back_node_id = "detail";
    const restoredProduct = {
      ...product,
      session_version: 4,
      projection_version: 4,
      event_cursor: 3,
    };
    restoredProduct.navigation = {
      ...restoredProduct.navigation,
      can_forward: true,
      forward_node_id: "cart",
    };
    const restoredCart = {
      ...cart,
      session_version: 5,
      projection_version: 5,
      event_cursor: 4,
    };
    client.enqueueSession(product);
    client.enqueueSession(cart);
    client.enqueueNavigation(restoredProduct);
    client.enqueueNavigation(restoredCart);
    const dispatchResult = {
      ...routeDeckDispatchResultFixture(),
      session_version: 3,
      projection_version: 3,
    };
    const dispatch = vi.spyOn(client, "dispatch").mockImplementation(async () => {
      client.emit(
        routeDeckEventFixture({
          cursor: 2,
          sessionVersion: 3,
          projectionVersion: 3,
        }),
      );
      return dispatchResult;
    });

    const history = new MemoryHistoryHarness("/items/item-public");
    const routes = createRouteDeckRouteCodec(contract, {
      validatePublicRouteKey: (_name, value) => value === "item-public",
      validateResumeCapability: () => true,
    });
    const store = createRouteDeckStore({
      client,
      history,
      routes,
      bootstrapMode: "resume",
      createRequestId: () => "restore-product-entry",
    });
    await store.bootstrap();

    await store.dispatch({
      operation_id: "cart.open",
      request_id: "open-cart",
      expected_session_version: 2,
      arguments: {},
    });

    expect(history.entries).toEqual(["/items/item-public", "/cart"]);
    expect(history.entryIds).toEqual([2, 3]);
    expect(history.current()).toBe("/cart");

    await store.cancel();
    await flushRouteDeckTasks();
    expect(history.current()).toBe("/items/item-public");
    expect(store.getState().projection?.current.node_id).toBe("detail");
    expect(client.navigationRequests[0]?.intent).toEqual({
      kind: "restore_history_entry",
      history_entry_id: 2,
      path: "/items/item-public",
    });

    store.forward();
    await flushRouteDeckTasks();
    expect(history.current()).toBe("/cart");
    expect(store.getState().projection?.current.node_id).toBe("cart");
    expect(client.navigationRequests[1]?.intent).toEqual({
      kind: "restore_history_entry",
      history_entry_id: 3,
      path: "/cart",
    });

    client.enqueueSession({
      ...restoredCart,
      session_version: 6,
      projection_version: 6,
      event_cursor: 5,
    });
    dispatch.mockImplementationOnce(async () => {
      client.emit(
        routeDeckEventFixture({
          cursor: 5,
          sessionVersion: 6,
          projectionVersion: 6,
        }),
      );
      throw new Error("response connection closed");
    });
    await expect(
      store.dispatch({
        operation_id: "cart.refresh",
        request_id: "refresh-cart",
        expected_session_version: 5,
        arguments: {},
      }),
    ).rejects.toThrow("response connection closed");
    await flushRouteDeckTasks();
    expect(store.getState().syncStatus).toBe("live");
    expect(store.getState().sessionVersion).toBe(6);
    expect(history.entries).toEqual(["/items/item-public", "/cart"]);
    store.dispose();
  });

  it("retains the exact failed session-create request for explicit bootstrap retry", async () => {
    const client = new ScriptedRouteDeckClient();
    const created = routeDeckProjectionFixture({
      nodeId: "home",
      routeTemplate: "/",
      sessionVersion: 1,
      projectionVersion: 1,
      eventCursor: 0,
    });
    const requests: Parameters<typeof client.createSession>[0][] = [];
    vi.spyOn(client, "createSession").mockImplementation(async (request) => {
      requests.push(request);
      if (requests.length === 1) {
        throw new RouteDeckOutcomeUnknownError(
          request.request_id,
          "Session creation response was lost.",
        );
      }
      return created;
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
    expect(store.getState().pendingBootstrap).toEqual({
      kind: "session_create",
    });
    expect(JSON.stringify(store.getState().pendingBootstrap)).not.toContain(
      "session-create-1",
    );

    await store.retrySessionCreate();

    expect(requests).toHaveLength(2);
    expect(requests[1]).toBe(requests[0]);
    expect(store.getState().pendingBootstrap).toBeNull();
    expect(store.getState().syncStatus).toBe("live");
    expect(client.calls).toContain("events.connect:0");
    store.dispose();
  });

  it("abandons a retained session-create attempt only by starting with a new request ID", async () => {
    const client = new ScriptedRouteDeckClient();
    const created = routeDeckProjectionFixture();
    const requests: Parameters<typeof client.createSession>[0][] = [];
    vi.spyOn(client, "createSession").mockImplementation(async (request) => {
      requests.push(request);
      if (requests.length === 1) {
        throw new RouteDeckOutcomeUnknownError(
          request.request_id,
          "Session creation response was lost.",
        );
      }
      return created;
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

    await store.startNewSession();

    expect(requests.map((request) => request.request_id)).toEqual([
      "session-create-1",
      "session-create-2",
    ]);
    expect(requests[1]).not.toBe(requests[0]);
    expect(store.getState().syncStatus).toBe("live");
    store.dispose();
  });

  it("exposes expired resume recovery without silently creating a session", async () => {
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
    expect(client.sessionCreateRequests).toHaveLength(0);
    expect(store.getState().pendingBootstrap).toEqual({
      kind: "resume_expired",
      status: 410,
    });

    await store.startNewSession();

    expect(client.sessionCreateRequests).toEqual([
      { request_id: "replacement-session-1" },
    ]);
    expect(store.getState().syncStatus).toBe("live");
    store.dispose();
  });

  it("requires explicit replacement when a no-cookie session-bound link cannot resume", async () => {
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
    const routes = createRouteDeckRouteCodec(
      routeDeckFrontendContractFixture(),
      { validateResumeCapability: () => false },
    );
    const store = createRouteDeckStore({
      client,
      history,
      routes,
      bootstrapMode: "resume_or_create_shareable",
      createRequestId: () => "replacement-missing-session-1",
    });

    await expect(store.bootstrap()).rejects.toMatchObject({ status: 404 });
    expect(client.sessionCreateRequests).toHaveLength(0);
    expect(store.getState().pendingBootstrap).toEqual({
      kind: "resume_missing",
      status: 404,
    });

    await store.startNewSession();

    expect(client.sessionCreateRequests).toEqual([
      { request_id: "replacement-missing-session-1" },
    ]);
    expect(store.getState().syncStatus).toBe("live");
    expect(history.current()).toBe("/");
    store.dispose();
  });

  it.each([
    {
      label: "expired",
      error: new RouteDeckHttpError(410, null, "The buyer session expired."),
      requestId: "replacement-expired-shareable-session-1",
    },
    {
      label: "contract-mismatched",
      error: new RouteDeckHttpError(
        409,
        {
          code: "session_upgrade_required",
          correlation_id: "correlation-contract-mismatch",
          kind: "state_conflict",
          phase: "session_lookup",
          public_message: "The buyer session contract changed.",
        },
        "The buyer session contract changed.",
      ),
      requestId: "replacement-contract-shareable-session-1",
    },
  ])(
    "automatically creates a fresh session when a $label session opens a shareable route",
    async ({ error, requestId }) => {
      const client = new ScriptedRouteDeckClient();
      vi.spyOn(client, "getSession").mockRejectedValue(error);
      client.enqueueCreatedSession(routeDeckProjectionFixture());
      const history = new MemoryHistoryHarness("/");
      const routes = createRouteDeckRouteCodec(
        routeDeckFrontendContractFixture(),
        { validateResumeCapability: () => false },
      );
      const store = createRouteDeckStore({
        client,
        history,
        routes,
        bootstrapMode: "resume_or_create_shareable",
        createRequestId: () => requestId,
      });

      await store.bootstrap();

      expect(client.sessionCreateRequests).toEqual([{ request_id: requestId }]);
      expect(store.getState().pendingBootstrap).toBeNull();
      expect(store.getState().syncStatus).toBe("live");
      expect(history.current()).toBe("/");
      store.dispose();
    },
  );

  it("keeps contract-mismatch replacement explicit on a session-bound route", async () => {
    const client = new ScriptedRouteDeckClient();
    vi.spyOn(client, "getSession").mockRejectedValue(
      new RouteDeckHttpError(
        409,
        {
          code: "session_upgrade_required",
          correlation_id: "correlation-secure-contract-mismatch",
          kind: "state_conflict",
          phase: "session_lookup",
          public_message: "The buyer session contract changed.",
        },
        "The buyer session contract changed.",
      ),
    );
    client.enqueueCreatedSession(routeDeckProjectionFixture());
    const history = new MemoryHistoryHarness(
      "/secure?resume_handle=resume-contract-mismatch",
    );
    const routes = createRouteDeckRouteCodec(
      routeDeckFrontendContractFixture(),
      { validateResumeCapability: () => true },
    );
    const store = createRouteDeckStore({
      client,
      history,
      routes,
      bootstrapMode: "resume_or_create_shareable",
      createRequestId: () => "replacement-secure-contract-session-1",
    });

    await expect(store.bootstrap()).rejects.toMatchObject({ status: 409 });

    expect(client.sessionCreateRequests).toHaveLength(0);
    expect(store.getState().pendingBootstrap).toEqual({
      kind: "resume_contract_mismatch",
      status: 409,
    });
    expect(history.current()).toBe(
      "/secure?resume_handle=resume-contract-mismatch",
    );
    store.dispose();
  });

  it("finishes bootstrap when an initial retained navigation is abandoned", async () => {
    const client = new ScriptedRouteDeckClient();
    const home = routeDeckProjectionFixture({
      nodeId: "home",
      routeTemplate: "/",
      sessionVersion: 1,
      projectionVersion: 1,
      eventCursor: 0,
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
    const restoredHome = {
      ...home,
      session_version: 3,
      projection_version: 3,
      event_cursor: 2,
    };
    client.enqueueSession(home);
    client.enqueueSession(product);
    let navigationCall = 0;
    vi.spyOn(client, "navigate").mockImplementation(async (request) => {
      client.navigationRequests.push(request);
      navigationCall += 1;
      if (navigationCall === 1) {
        throw new RouteDeckOutcomeUnknownError(
          request.request_id,
          "Initial navigation response was lost.",
        );
      }
      return restoredHome;
    });
    const history = new MemoryHistoryHarness("/items/item-public");
    const routes = createRouteDeckRouteCodec(routeDeckFrontendContractFixture(), {
      validatePublicRouteKey: (_name, value) => value === "item-public",
      validateResumeCapability: () => false,
    });
    let requestSequence = 0;
    const store = createRouteDeckStore({
      client,
      history,
      routes,
      bootstrapMode: "resume",
      createRequestId: () => `navigation-${++requestSequence}`,
    });

    await expect(store.bootstrap()).rejects.toBeInstanceOf(
      RouteDeckOutcomeUnknownError,
    );
    expect(store.getState().pendingNavigation?.requestId).toBe("navigation-1");
    expect(client.calls.some((call) => call.startsWith("events.connect"))).toBe(
      false,
    );

    await store.abandonNavigation();

    expect(store.getState().pendingNavigation).toBeNull();
    expect(store.getState().syncStatus).toBe("live");
    expect(history.entries).toEqual(["/", "/items/item-public"]);
    expect(client.calls).toContain("events.connect:1");

    history.back();
    await flushRouteDeckTasks();
    expect(client.navigationRequests[1]?.intent).toEqual({
      kind: "restore_history_entry",
      history_entry_id: 1,
      path: "/",
    });
    store.dispose();
  });

  it("invalidates the old event generation before an authoritative resync GET", async () => {
    const client = new ScriptedRouteDeckClient();
    const initial = routeDeckProjectionFixture({
      sessionVersion: 1,
      projectionVersion: 1,
      eventCursor: 0,
    });
    const authoritative = routeDeckProjectionFixture({
      sessionVersion: 3,
      projectionVersion: 2,
      eventCursor: 4,
    });
    let resolveAuthoritative!: (projection: typeof authoritative) => void;
    let sessionCall = 0;
    vi.spyOn(client, "getSession").mockImplementation(() => {
      sessionCall += 1;
      if (sessionCall === 1) return Promise.resolve(initial);
      return new Promise((resolve) => {
        resolveAuthoritative = resolve;
      });
    });
    const streams: Array<{
      options: Parameters<typeof client.connectEvents>[0];
      close: ReturnType<typeof vi.fn>;
    }> = [];
    vi.spyOn(client, "connectEvents").mockImplementation((options) => {
      const close = vi.fn();
      streams.push({ options, close });
      options.onOpen?.({ after: options.after, reconnecting: false });
      return { close, done: new Promise<void>(() => undefined) };
    });
    const store = createRouteDeckStore({ client, bootstrapMode: "resume" });
    await store.bootstrap();

    const resync = store.resync();
    await flushRouteDeckTasks(2);
    expect(streams[0]?.close).toHaveBeenCalledOnce();
    streams[0]?.options.onEvent(
      routeDeckEventFixture({
        cursor: 1,
        sessionVersion: 2,
        projectionVersion: 1,
      }),
    );
    expect(store.getState().syncStatus).toBe("resyncing");
    expect(store.getState().eventCursor).toBe(0);

    resolveAuthoritative(authoritative);
    await resync;
    expect(streams[1]?.options.after).toBe(4);
    streams[1]?.options.onEvent(
      routeDeckEventFixture({
        cursor: 5,
        sessionVersion: 4,
        projectionVersion: 2,
      }),
    );
    expect(store.getState().eventCursor).toBe(5);
    expect(store.getState().syncStatus).toBe("live");
    store.dispose();
  });

  it("resyncs the current session after initial stream failure and finishes bootstrap wiring", async () => {
    const client = new ScriptedRouteDeckClient();
    const initial = routeDeckProjectionFixture({
      nodeId: "home",
      routeTemplate: "/",
      sessionVersion: 1,
      projectionVersion: 1,
      eventCursor: 0,
      historyEntryId: 1,
    });
    const authoritative = {
      ...initial,
      session_version: 2,
      projection_version: 2,
      event_cursor: 1,
    };
    const product = routeDeckProjectionFixture({
      nodeId: "detail",
      routeTemplate: "/items/{item_handle}",
      routeParams: [{ name: "item_handle", value: "item-public" }],
      sessionVersion: 3,
      projectionVersion: 3,
      eventCursor: 2,
      historyEntryId: 2,
    });
    client.enqueueSession(initial);
    client.enqueueSession(authoritative);
    client.enqueueNavigation(product);
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
    const history = new MemoryHistoryHarness("/");
    const routes = createRouteDeckRouteCodec(routeDeckFrontendContractFixture(), {
      validatePublicRouteKey: (_name, value) => value === "item-public",
      validateResumeCapability: () => false,
    });
    const store = createRouteDeckStore({
      client,
      history,
      routes,
      bootstrapMode: "resume",
      createRequestId: () => "history-after-resync-1",
    });

    await expect(store.bootstrap()).rejects.toMatchObject({
      code: "stream_failed",
    });
    expect(store.getState().projection).not.toBeNull();
    expect(store.getState().pendingBootstrap).toBeNull();
    expect(store.getState().pendingNavigation).toBeNull();

    await store.resync();

    expect(store.getState().syncStatus).toBe("live");
    expect(client.calls).toContain("session.get");
    history.pop("/items/item-public", 2);
    await flushRouteDeckTasks();
    expect(client.navigationRequests[0]?.intent).toEqual({
      kind: "restore_history_entry",
      history_entry_id: 2,
      path: "/items/item-public",
    });
    store.dispose();
  });
});
