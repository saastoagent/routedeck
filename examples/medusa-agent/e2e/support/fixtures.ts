import {
  expect,
  test as base,
  type BrowserContext,
  type ConsoleMessage,
  type Page,
  type Response,
} from "@playwright/test";

export interface BrowserSafety {
  readonly forbiddenRequests: readonly string[];
  readonly httpFailures: readonly string[];
  readonly networkEvents: readonly SanitizedBrowserNetworkEvent[];
  readonly runtimeErrors: readonly string[];
  assertClean(): void;
}

export interface SanitizedBrowserNetworkEvent {
  readonly schema_version: 1;
  readonly sequence: number;
  readonly context: "primary" | "anonymous";
  readonly phase: "request" | "response";
  readonly method: string;
  readonly origin: string;
  readonly path_template: string;
  readonly query_parameter_names: readonly string[];
  readonly resource_type: string;
  readonly status?: number;
}

interface MutableBrowserSafety extends BrowserSafety {
  forbiddenRequests: string[];
  httpFailures: string[];
  networkEvents: SanitizedBrowserNetworkEvent[];
  runtimeErrors: string[];
}

export async function installBrowserSafety(
  context: BrowserContext,
  contextRole: "primary" | "anonymous" = "primary",
): Promise<BrowserSafety> {
  const safety: MutableBrowserSafety = {
    forbiddenRequests: [],
    httpFailures: [],
    networkEvents: [],
    runtimeErrors: [],
    assertClean() {
      expect(
        this.forbiddenRequests,
        "The browser must never call Medusa directly or access a Store API path.",
      ).toEqual([]);
      expect(
        this.httpFailures,
        "The buyer flow must not receive an unexpected HTTP failure.",
      ).toEqual([]);
      expect(
        this.runtimeErrors,
        "The rendered buyer flow must not emit browser runtime errors.",
      ).toEqual([]);
    },
  };

  const trackPage = (page: Page) => {
    page.on("request", (request) => {
      safety.networkEvents.push(
        networkEvent(safety.networkEvents.length + 1, contextRole, "request", request),
      );
    });
    page.on("pageerror", (error) => {
      safety.runtimeErrors.push(`pageerror: ${error.message}`);
    });
    page.on("response", (response: Response) => {
      safety.networkEvents.push(
        networkEvent(
          safety.networkEvents.length + 1,
          contextRole,
          "response",
          response.request(),
          response.status(),
        ),
      );
      if (response.status() < 400 || isExpectedSessionMiss(response)) return;
      const request = response.request();
      const url = new URL(response.url());
      safety.httpFailures.push(
        `${response.status()} ${request.method()} ${url.origin}${pathTemplate(url)}`,
      );
    });
    page.on("console", (message: ConsoleMessage) => {
      if (
        message.type() === "error" &&
        message.text() !==
          "Failed to load resource: the server responded with a status of 404 (Not Found)"
      ) {
        safety.runtimeErrors.push(`console: ${message.text()}`);
      }
    });
  };
  context.pages().forEach(trackPage);
  context.on("page", trackPage);

  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const storePath =
      url.pathname === "/store" || url.pathname.startsWith("/store/");
    if (url.port === "9100" || storePath) {
      safety.forbiddenRequests.push(
        `${request.method()} ${url.origin}${pathTemplate(url)}`,
      );
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });

  return safety;
}

interface SafetyFixtures {
  browserSafety: BrowserSafety;
}

export const test = base.extend<SafetyFixtures>({
  browserSafety: [
    async ({ context }, use, testInfo) => {
      const safety = await installBrowserSafety(context);
      await use(safety);
      if (
        safety.forbiddenRequests.length > 0 ||
        safety.httpFailures.length > 0 ||
        safety.runtimeErrors.length > 0
      ) {
        await testInfo.attach("browser-safety.json", {
          body: Buffer.from(
            JSON.stringify(
              {
                forbiddenRequests: safety.forbiddenRequests,
                httpFailures: safety.httpFailures,
                runtimeErrors: safety.runtimeErrors,
              },
              null,
              2,
            ),
          ),
          contentType: "application/json",
        });
      }
      safety.assertClean();
    },
    { auto: true },
  ],
});

function isExpectedSessionMiss(response: Response): boolean {
  const request = response.request();
  return (
    response.status() === 404 &&
    request.method() === "GET" &&
    new URL(response.url()).pathname === "/api/routedeck/session"
  );
}

function networkEvent(
  sequence: number,
  context: "primary" | "anonymous",
  phase: "request" | "response",
  request: import("@playwright/test").Request,
  status?: number,
): SanitizedBrowserNetworkEvent {
  const url = new URL(request.url());
  return {
    schema_version: 1,
    sequence,
    context,
    phase,
    method: request.method(),
    origin: url.origin,
    path_template: pathTemplate(url),
    query_parameter_names: [...url.searchParams.keys()].sort(),
    resource_type: request.resourceType(),
    ...(status === undefined ? {} : { status }),
  };
}

function pathTemplate(url: URL): string {
  const segments = url.pathname.split("/").filter(Boolean);
  if (
    segments.length === 3 &&
    segments[0] === "orders" &&
    segments[2] === "confirmation"
  ) {
    return "/orders/{confirmation_handle}/confirmation";
  }
  if (
    segments.length === 5 &&
    segments[0] === "api" &&
    segments[1] === "routedeck" &&
    segments[2] === "reviews" &&
    segments[4] === "accept"
  ) {
    return "/api/routedeck/reviews/{review_id}/accept";
  }
  if (
    segments.length === 4 &&
    segments[0] === "api" &&
    segments[1] === "routedeck" &&
    segments[2] === "private-forms"
  ) {
    return "/api/routedeck/private-forms/{form_id}";
  }
  return url.pathname;
}

export { expect };
