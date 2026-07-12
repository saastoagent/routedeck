import { expect, it } from "vitest";
import {
  routeDeckFrontendContractFixture,
  routeDeckProjectionFixture,
  ScriptedRouteDeckClient,
} from "@routedeck/testing";

import { createMedusaRouteDeck } from "../app/createRouteDeck";

it("uses the bootstrapped projection as the exact session-bound route context", async () => {
  const client = new ScriptedRouteDeckClient();
  const projection = routeDeckProjectionFixture({
    nodeId: "secure",
    routeTemplate: "/secure",
  });
  projection.navigation.resume_handle = "resume-current";
  client.enqueueSession(projection);
  window.history.replaceState(
    null,
    "",
    "/secure?resume_handle=resume-current",
  );

  const routeDeck = createMedusaRouteDeck({
    contract: routeDeckFrontendContractFixture(),
    browser: window,
    client,
  });

  try {
    expect(() =>
      routeDeck.routes.decode("/secure?resume_handle=resume-current", {
        sessionAvailable: false,
      }),
    ).toThrowError(/requires the current cookie-backed session/);

    await routeDeck.store.bootstrap();

    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/secure?resume_handle=resume-current",
    );
    expect(() =>
      routeDeck.routes.decode("/secure?resume_handle=resume-other", {
        sessionAvailable: true,
      }),
    ).toThrowError(/resume capability is unavailable or mismatched/);
  } finally {
    routeDeck.store.dispose();
    window.history.replaceState(null, "", "/");
  }
});
