import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor } from "@testing-library/react";
import { StrictMode, type ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import {
  createPrivateFormState,
  createRouteDeckStore,
  type RouteDeckPrivateFormSnapshot,
  type RouteDeckPrivateFormState,
} from "@routedeck/core";
import {
  RouteDeckPrivateForm,
  RouteDeckProvider,
} from "@routedeck/react";
import {
  routeDeckFrontendContractFixture,
  routeDeckProjectionFixture,
  ScriptedRouteDeckClient,
} from "@routedeck/testing";

const CACHED_FORM_ID = "form_opaque_cached_review";
const OBSOLETE_FORM_ID = "form_opaque_obsolete_mount";
const CURRENT_FORM_ID = "form_opaque_current_mount";

describe("RouteDeck private-form mount lifecycle", () => {
  it("reuses a cached snapshot without a StrictMode duplicate load", async () => {
    const client = new ScriptedRouteDeckClient();
    const store = createBootstrappedStore(client);
    await store.bootstrap();
    const privateForms = createPrivateFormState(client.privateForms);
    client.privateValues.set(CACHED_FORM_ID, snapshot(CACHED_FORM_ID));
    await privateForms.load(CACHED_FORM_ID);
    const load = vi.spyOn(privateForms, "load");

    const rendered = render(
      provider(
        store,
        privateForms,
        <StrictMode>
          <PrivateFormProbe formId={CACHED_FORM_ID} />
        </StrictMode>,
      ),
    );

    expect(screen.getByTestId("private-form-snapshot")).toHaveTextContent(
      CACHED_FORM_ID,
    );
    expect(load).not.toHaveBeenCalled();

    rendered.unmount();
    privateForms.dispose();
    store.dispose();
  });

  it("aborts an obsolete mount load and does not surface AbortError", async () => {
    const client = new ScriptedRouteDeckClient();
    const store = createBootstrappedStore(client);
    await store.bootstrap();
    const obsoleteSignals: AbortSignal[] = [];
    const load = vi.fn(
      (
        formId: string,
        options: { signal?: AbortSignal } = {},
      ): Promise<RouteDeckPrivateFormSnapshot> => {
        if (formId === CURRENT_FORM_ID) {
          return Promise.resolve(snapshot(CURRENT_FORM_ID));
        }
        const signal = options.signal;
        if (signal === undefined) {
          throw new Error("Mount loads must provide an AbortSignal.");
        }
        obsoleteSignals.push(signal);
        return new Promise((_, reject) => {
          signal.addEventListener(
            "abort",
            () => reject(signal.reason),
            { once: true },
          );
        });
      },
    );
    const privateForms: RouteDeckPrivateFormState = {
      get: () => null,
      load,
      save: vi.fn(async () => {
        throw new Error("save is outside this mount lifecycle test");
      }),
      getPendingSave: () => null,
      retrySave: vi.fn(async () => {
        throw new Error("retry is outside this mount lifecycle test");
      }),
      abandonPendingSave: vi.fn(),
      clear: vi.fn(),
      dispose: vi.fn(),
    };

    const rendered = render(
      provider(
        store,
        privateForms,
        <PrivateFormProbe formId={OBSOLETE_FORM_ID} />,
      ),
    );
    await waitFor(() => expect(load).toHaveBeenCalledTimes(1));

    rendered.rerender(
      provider(
        store,
        privateForms,
        <PrivateFormProbe formId={CURRENT_FORM_ID} />,
      ),
    );

    await waitFor(() =>
      expect(screen.getByTestId("private-form-snapshot")).toHaveTextContent(
        CURRENT_FORM_ID,
      ),
    );
    expect(obsoleteSignals).toHaveLength(1);
    expect(obsoleteSignals[0]?.aborted).toBe(true);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    rendered.unmount();
    store.dispose();
  });
});

function PrivateFormProbe({ formId }: { formId: string }) {
  return (
    <RouteDeckPrivateForm formId={formId} loadOnMount>
      {(binding) => (
        <>
          <output data-testid="private-form-snapshot">
            {binding.snapshot?.form_id ?? "none"}
          </output>
          {binding.error === null ? null : (
            <p role="alert">{binding.error.message}</p>
          )}
        </>
      )}
    </RouteDeckPrivateForm>
  );
}

function provider(
  store: ReturnType<typeof createRouteDeckStore>,
  privateForms: RouteDeckPrivateFormState,
  child: ReactElement,
) {
  return (
    <RouteDeckProvider
      store={store}
      contract={routeDeckFrontendContractFixture()}
      privateForms={privateForms}
    >
      {child}
    </RouteDeckProvider>
  );
}

function createBootstrappedStore(client: ScriptedRouteDeckClient) {
  client.enqueueSession(routeDeckProjectionFixture());
  return createRouteDeckStore({ client, bootstrapMode: "resume" });
}

function snapshot(formId: string): RouteDeckPrivateFormSnapshot {
  return {
    form_id: formId,
    revision: 1,
    complete: true,
    session_version: 2,
    value: {},
  };
}
