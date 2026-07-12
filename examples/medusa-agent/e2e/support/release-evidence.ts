import { createHash } from "node:crypto";
import { mkdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import type {
  BrowserContext,
  Page,
  Response,
  TestInfo,
} from "@playwright/test";

import type {
  BrowserSafety,
  SanitizedBrowserNetworkEvent,
} from "./fixtures";

export type BrowserEvidenceStage =
  | "browse"
  | "cart"
  | "review-pending"
  | "confirmation";

export interface BrowserFlowEvidence {
  capture(page: Page, stage: BrowserEvidenceStage): Promise<void>;
  registerSensitiveValues(values: readonly string[]): void;
}

const SCREENSHOT_FILES: Readonly<Record<BrowserEvidenceStage, string>> =
  Object.freeze({
    browse: "browse.png",
    cart: "cart.png",
    "review-pending": "review-pending.png",
    confirmation: "confirmation.png",
  });

const ROUTE_TEMPLATES: Readonly<Record<BrowserEvidenceStage, string>> =
  Object.freeze({
    browse: "/products",
    cart: "/cart",
    "review-pending": "/checkout/review",
    confirmation: "/orders/{confirmation_handle}/confirmation",
  });

interface ScreenshotMeasurement {
  readonly stage: BrowserEvidenceStage;
  readonly file: string;
  readonly route_template: string;
  readonly byte_count: number;
  readonly sha256: string;
  readonly masked_element_count: number;
}

export class ReleaseBrowserEvidence implements BrowserFlowEvidence {
  readonly #browserDir: string;
  readonly #rawDir: string;
  readonly #measurements: ScreenshotMeasurement[] = [];
  readonly #supervisionRows: Array<Record<string, unknown>> = [];
  readonly #pendingSupervisionCaptures: Promise<void>[] = [];
  readonly #sensitiveValues = new Set<string>();
  #confirmationUrl: string | undefined;
  #traceStarted = false;

  constructor(
    bundleRoot: string,
    rawDir: string,
    private readonly context: BrowserContext,
  ) {
    this.#browserDir = path.join(bundleRoot, "browser");
    this.#rawDir = rawDir;
  }

  async start(): Promise<void> {
    if (this.#traceStarted) {
      throw new Error("Release browser trace was started twice.");
    }
    await mkdir(this.#browserDir, { recursive: true });
    await mkdir(this.#rawDir, { recursive: true });
    await this.context.tracing.start({
      screenshots: false,
      snapshots: false,
      sources: false,
      title: "RouteDeck measured buyer flow",
    });
    this.context.on("response", (response) => {
      this.#pendingSupervisionCaptures.push(
        this.#captureSupervisionResponse(response),
      );
    });
    this.#traceStarted = true;
  }

  registerSensitiveValues(values: readonly string[]): void {
    for (const value of values) {
      const normalized = value.trim();
      if (normalized.length > 0) this.#sensitiveValues.add(normalized);
    }
  }

  async capture(page: Page, stage: BrowserEvidenceStage): Promise<void> {
    if (this.#measurements.some((event) => event.stage === stage)) {
      throw new Error(`Release browser stage ${stage} was captured twice.`);
    }
    const privateMasks =
      stage === "review-pending"
        ? [
            page.locator("address"),
            page.locator('[aria-labelledby="private-address-summary-title"]'),
          ]
        : [];
    const maskedElementCount = await countLocatedElements(privateMasks);
    if (stage === "review-pending" && maskedElementCount === 0) {
      throw new Error("Review screenshot has no located private address to mask.");
    }
    const file = SCREENSHOT_FILES[stage];
    const observedRouteTemplate = routeTemplateForCapture(page.url(), stage);
    if (observedRouteTemplate !== ROUTE_TEMPLATES[stage]) {
      throw new Error(
        `Release screenshot ${stage} observed unexpected route ${observedRouteTemplate}.`,
      );
    }
    const image = await page.screenshot({
      path: path.join(this.#browserDir, file),
      fullPage: true,
      animations: "disabled",
      mask: privateMasks,
    });
    if (image.byteLength === 0) {
      throw new Error(`Release screenshot ${file} is empty.`);
    }
    this.#measurements.push({
      stage,
      file,
      route_template: observedRouteTemplate,
      byte_count: image.byteLength,
      sha256: createHash("sha256").update(image).digest("hex"),
      masked_element_count: maskedElementCount,
    });
    if (stage === "confirmation") this.#confirmationUrl = page.url();
  }

  async finalize(
    primaryContext: BrowserSafety,
    anonymousContext: BrowserSafety,
  ): Promise<void> {
    const expectedStages = Object.keys(SCREENSHOT_FILES).sort();
    const capturedStages = this.#measurements
      .map((event) => event.stage)
      .sort();
    if (JSON.stringify(capturedStages) !== JSON.stringify(expectedStages)) {
      throw new Error(
        `Release browser evidence is incomplete: ${capturedStages.join(", ")}.`,
      );
    }
    primaryContext.assertClean();
    anonymousContext.assertClean();
    await Promise.all(this.#pendingSupervisionCaptures);
    if (this.#supervisionRows.length === 0) {
      throw new Error("No measured RouteDeck supervision responses were captured.");
    }
    if (!this.#traceStarted) {
      throw new Error("Release browser trace was not started.");
    }

    const rawTracePath = path.join(this.#rawDir, "full-flow-trace.raw.zip");
    await this.context.tracing.stop({ path: rawTracePath });
    this.#traceStarted = false;
    const rawTrace = await stat(rawTracePath);
    if (rawTrace.size === 0) {
      throw new Error("Playwright produced an empty raw trace archive.");
    }
    await writeFile(
      path.join(this.#rawDir, "sensitive-values.json"),
      `${JSON.stringify([...this.#sensitiveValues])}\n`,
      "utf8",
    );
    const runtimeDir = path.join(path.dirname(this.#browserDir), "runtime");
    await mkdir(runtimeDir, { recursive: true });
    await writeFile(
      path.join(runtimeDir, "supervision-trace.ndjson"),
      `${this.#supervisionRows.map((row) => JSON.stringify(row)).join("\n")}\n`,
      "utf8",
    );
    if (this.#confirmationUrl === undefined) {
      throw new Error("Confirmation URL was not measured before persistence probe setup.");
    }
    const runId = process.env.ROUTEDECK_RELEASE_RUN_ID;
    if (runId === undefined || runId.trim().length === 0) {
      throw new Error("ROUTEDECK_RELEASE_RUN_ID is required for release evidence.");
    }
    await this.context.storageState({
      path: path.join(this.#rawDir, "persistence-storage-state.json"),
    });
    await writeFile(
      path.join(this.#rawDir, "persistence-input.json"),
      `${JSON.stringify({
        schema_version: 1,
        run_id: runId,
        confirmation_url: this.#confirmationUrl,
        route_template: "/orders/{confirmation_handle}/confirmation",
        pre_restart_confirmation_observed: true,
      })}\n`,
      "utf8",
    );

    const networkEvents = mergeNetworkEvents(
      primaryContext.networkEvents,
      anonymousContext.networkEvents,
    );
    const serializedEvents = networkEvents.map((event) =>
      JSON.stringify(event),
    );
    await writeFile(
      path.join(this.#browserDir, "network-events.ndjson"),
      `${serializedEvents.join("\n")}\n`,
      "utf8",
    );

    const directStoreRequestCount =
      primaryContext.forbiddenRequests.length +
      anonymousContext.forbiddenRequests.length;
    const piiCaptureCount = countSensitiveCaptures(
      serializedEvents,
      this.#sensitiveValues,
    );
    const rawPrivateIdCaptureCount = serializedEvents.filter((row) =>
      containsRawPrivateIdentifier(row),
    ).length;
    const requestCount = networkEvents.filter(
      (event) => event.phase === "request",
    ).length;
    const responseCount = networkEvents.filter(
      (event) => event.phase === "response",
    ).length;
    const screenshotsSanitized =
      this.#measurements.length === expectedStages.length &&
      this.#measurements.every(
        (item) =>
          item.byte_count > 0 &&
          item.sha256.length === 64 &&
          (item.stage !== "review-pending" || item.masked_element_count > 0),
      );

    await writeFile(
      path.join(this.#browserDir, "network-boundary.json"),
      `${JSON.stringify(
        {
          schema_version: 1,
          status: "pending_trace_sanitization",
          capture_source: "playwright_page_request_and_response_events",
          captured_network_fields: [
            "method",
            "origin",
            "path_template",
            "query_parameter_names",
            "resource_type",
            "status",
          ],
          request_count: requestCount,
          response_count: responseCount,
          direct_store_request_count: directStoreRequestCount,
          pii_capture_count: piiCaptureCount,
          raw_private_id_capture_count: rawPrivateIdCaptureCount,
          screenshots_sanitized: screenshotsSanitized,
          screenshot_measurements: this.#measurements,
          trace_sanitized: false,
          trace_capture: {
            source: "playwright_context_tracing",
            raw_archive_byte_count: rawTrace.size,
            snapshots_enabled: false,
            screenshots_enabled: false,
            sources_enabled: false,
          },
          enforced_browser_denials: ["tcp_port_9100", "path_prefix_/store/"],
          isolated_context_count: new Set(
            networkEvents.map((event) => event.context),
          ).size,
        },
        null,
        2,
      )}\n`,
      "utf8",
    );
  }

  async #captureSupervisionResponse(response: Response): Promise<void> {
    const request = response.request();
    const pathTemplate = supervisionPathTemplate(new URL(response.url()));
    if (
      request.method() !== "POST" ||
      pathTemplate === undefined ||
      !response.ok()
    ) {
      return;
    }
    const value: unknown = await response.json();
    if (!isRecord(value)) {
      throw new Error("RouteDeck supervision response must be an object.");
    }
    const evidence = value.evidence;
    if (!isRecord(evidence)) {
      throw new Error("RouteDeck supervision response has no evidence object.");
    }
    const operationId = requiredString(value.operation_id, "operation_id");
    const disposition = requiredString(value.disposition, "disposition");
    const source = requiredString(evidence.source, "evidence.source");
    const phases = evidence.phases;
    if (!Array.isArray(phases) || !phases.every((item) => typeof item === "string")) {
      throw new Error("RouteDeck supervision phases must be strings.");
    }
    this.#supervisionRows.push({
      schema_version: 1,
      sequence: this.#supervisionRows.length + 1,
      source: "playwright_captured_routedeck_operation_response",
      transport_path_template: pathTemplate,
      operation_id: operationId,
      disposition,
      outcome: typeof value.outcome === "string" ? value.outcome : null,
      operation_source: source,
      phases,
      delivery_phase:
        typeof evidence.delivery_phase === "string"
          ? evidence.delivery_phase
          : null,
      session_version: requiredNumber(value.session_version, "session_version"),
      projection_version: requiredNumber(
        value.projection_version,
        "projection_version",
      ),
      review_present: value.review !== null && value.review !== undefined,
      failure_present: value.failure !== null && value.failure !== undefined,
    });
  }
}

export async function writeMeasuredSseTrace(
  response: Response,
  testInfo: TestInfo,
): Promise<void> {
  const bundleRoot = process.env.ROUTEDECK_RELEASE_BUNDLE;
  if (bundleRoot === undefined || testInfo.project.name !== "desktop-chromium") {
    return;
  }
  const events = parseSse(await response.text());
  if (
    events.length === 0 ||
    events[0]?.event !== "stream_start" ||
    events.at(-1)?.event !== "stream_end"
  ) {
    throw new Error("Measured chat response is not a complete SSE stream.");
  }
  const runtimeDir = path.join(bundleRoot, "runtime");
  await mkdir(runtimeDir, { recursive: true });
  await writeFile(
    path.join(runtimeDir, "sse-trace.ndjson"),
    `${events
      .map((event, index) =>
        JSON.stringify({
          schema_version: 1,
          sequence: index + 1,
          source: "playwright_captured_sse_response",
          event: event.event,
          data_fields: Object.keys(event.data).sort(),
          status:
            typeof event.data.status === "string" ? event.data.status : null,
          operation_id:
            typeof event.data.operation_id === "string"
              ? event.data.operation_id
              : null,
        }),
      )
      .join("\n")}\n`,
    "utf8",
  );
}

export async function releaseEvidenceFor(
  testInfo: TestInfo,
  page: Page,
): Promise<ReleaseBrowserEvidence | undefined> {
  const bundleRoot = process.env.ROUTEDECK_RELEASE_BUNDLE;
  if (bundleRoot === undefined || testInfo.project.name !== "desktop-chromium") {
    return undefined;
  }
  const rawDir = process.env.ROUTEDECK_RELEASE_RAW_DIR;
  if (bundleRoot.trim().length === 0 || rawDir?.trim().length === 0) {
    throw new Error(
      "ROUTEDECK_RELEASE_BUNDLE and ROUTEDECK_RELEASE_RAW_DIR must be non-empty when set.",
    );
  }
  if (rawDir === undefined) {
    throw new Error("ROUTEDECK_RELEASE_RAW_DIR is required for release tracing.");
  }
  const evidence = new ReleaseBrowserEvidence(
    bundleRoot,
    rawDir,
    page.context(),
  );
  await evidence.start();
  return evidence;
}

async function countLocatedElements(
  locators: readonly ReturnType<Page["locator"]>[],
): Promise<number> {
  const counts = await Promise.all(locators.map((locator) => locator.count()));
  return counts.reduce((total, count) => total + count, 0);
}

function mergeNetworkEvents(
  primary: readonly SanitizedBrowserNetworkEvent[],
  anonymous: readonly SanitizedBrowserNetworkEvent[],
): SanitizedBrowserNetworkEvent[] {
  return [...primary, ...anonymous].map((event, index) => ({
    ...event,
    sequence: index + 1,
  }));
}

function countSensitiveCaptures(
  rows: readonly string[],
  values: ReadonlySet<string>,
): number {
  let count = 0;
  for (const row of rows) {
    for (const value of values) {
      if (row.includes(value)) count += 1;
    }
  }
  return count;
}

function containsRawPrivateIdentifier(value: string): boolean {
  return /(?:^|[^A-Za-z0-9])(?:cart|order|prod|variant|item|line|li|litem|so|reg|sc|pay)_[A-Za-z0-9]{16,}/.test(
    value,
  );
}

function routeTemplateForCapture(
  rawUrl: string,
  stage: BrowserEvidenceStage,
): string {
  const pathname = new URL(rawUrl).pathname;
  if (stage !== "confirmation") return pathname;
  const segments = pathname.split("/").filter(Boolean);
  if (
    segments.length === 3 &&
    segments[0] === "orders" &&
    segments[2] === "confirmation"
  ) {
    return "/orders/{confirmation_handle}/confirmation";
  }
  return pathname;
}

function supervisionPathTemplate(url: URL): string | undefined {
  if (url.pathname === "/api/routedeck/dispatch") {
    return url.pathname;
  }
  const segments = url.pathname.split("/").filter(Boolean);
  if (
    segments.length === 5 &&
    segments[0] === "api" &&
    segments[1] === "routedeck" &&
    segments[2] === "reviews" &&
    segments[4] === "accept"
  ) {
    return "/api/routedeck/reviews/{review_id}/accept";
  }
  return undefined;
}

function parseSse(body: string): Array<{
  event: string;
  data: Record<string, unknown>;
}> {
  const events: Array<{ event: string; data: Record<string, unknown> }> = [];
  let eventName: string | undefined;
  let eventData: Record<string, unknown> | undefined;
  for (const line of [...body.split(/\r?\n/), ""]) {
    if (line.startsWith("event: ")) {
      eventName = line.slice("event: ".length);
    } else if (line.startsWith("data: ")) {
      const parsed: unknown = JSON.parse(line.slice("data: ".length));
      if (!isRecord(parsed)) throw new Error("SSE data must be a JSON object.");
      eventData = parsed;
    } else if (line === "" && eventName !== undefined && eventData !== undefined) {
      events.push({ event: eventName, data: eventData });
      eventName = undefined;
      eventData = undefined;
    }
  }
  return events;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredString(value: unknown, label: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${label} must be a non-empty string.`);
  }
  return value;
}

function requiredNumber(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new Error(`${label} must be a non-negative integer.`);
  }
  return value;
}
