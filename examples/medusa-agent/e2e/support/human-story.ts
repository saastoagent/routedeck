import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  expect,
  type Locator,
  type Page,
  type Response,
} from "@playwright/test";

export const HUMAN_STORIES = Object.freeze({
  "US-01": "01-curious-newcomer",
  "US-02": "02-goal-led-discovery",
  "US-03": "03-changes-mind",
  "US-04": "04-hybrid-cart-management",
  "US-05": "05-thoughtful-checkout",
} as const);

export type HumanStoryId = keyof typeof HUMAN_STORIES;

export interface HumanStoryEvent {
  readonly at_ms: number;
  readonly kind:
    | "route"
    | "user"
    | "assistant"
    | "network"
    | "console"
    | "selection"
    | "assertion";
  readonly detail: Readonly<Record<string, unknown>>;
}

export interface HumanStoryEvidence {
  readonly schema_version: 1;
  readonly story_id: HumanStoryId;
  readonly title: string;
  readonly viewport: { readonly width: 1920; readonly height: 1080 };
  readonly video_size: { readonly width: 1920; readonly height: 1080 };
  readonly started_at: string;
  readonly duration_ms: number;
  readonly outcome: "passed" | "failed";
  readonly error: null | { readonly name: string; readonly message: string };
  readonly events: readonly HumanStoryEvent[];
  readonly visible_failures: readonly string[];
}

export interface RenderedProduct {
  readonly handle: string;
  readonly title: string;
}

export interface RenderedVariant {
  readonly label: string;
  readonly value: string;
}

export interface HumanBuyerProfile {
  readonly email: string;
  readonly firstName: string;
  readonly lastName: string;
  readonly address1: string;
  readonly city: string;
  readonly province: string;
  readonly postalCode: string;
  readonly countryLabel: string;
  readonly phone: string;
}

const CHAT_PATH = "/api/routedeck/chat";
const FINALIZED_ASSISTANT_SELECTOR =
  '[data-agent-message="assistant"][data-agent-message-status="finalized"]';
const CHAT_ERROR_SELECTOR = "[data-agent-chat-error]";
const CHAT_TIMEOUT_MS = 150_000;

export class HumanStoryRecorder {
  readonly #events: HumanStoryEvent[] = [];
  readonly #startedAt = new Date();
  readonly #startedMs = Date.now();

  constructor(
    readonly storyId: HumanStoryId,
    readonly title: string,
    private readonly page: Page,
  ) {
    page.on("framenavigated", (frame) => {
      if (frame !== page.mainFrame()) return;
      this.record("route", { path: safePath(frame.url()) });
    });
    page.on("console", (message) => {
      if (message.type() !== "warning" && message.type() !== "error") return;
      this.record("console", {
        level: message.type(),
        message: message.text(),
      });
    });
    page.on("pageerror", (error) => {
      this.record("console", { level: "pageerror", message: error.message });
    });
    page.on("response", (response) => {
      const url = new URL(response.url());
      if (!url.pathname.startsWith("/api/routedeck")) return;
      this.record("network", {
        method: response.request().method(),
        path_template: publicPathTemplate(url.pathname),
        status: response.status(),
      });
    });
  }

  record(kind: HumanStoryEvent["kind"], detail: Record<string, unknown>): void {
    this.#events.push({
      at_ms: Date.now() - this.#startedMs,
      kind,
      detail,
    });
  }

  async capture(stage: string, masks: readonly Locator[] = []): Promise<void> {
    const screenshotDir = path.join(artifactRoot(), "screenshots");
    await mkdir(screenshotDir, { recursive: true });
    const safeStage = stage.replace(/[^a-z0-9-]+/gi, "-").toLowerCase();
    await this.page.screenshot({
      path: path.join(
        screenshotDir,
        `${HUMAN_STORIES[this.storyId]}-${safeStage}.png`,
      ),
      fullPage: false,
      animations: "disabled",
      mask: [...masks],
    });
  }

  async finalize(
    outcome: "passed" | "failed",
    caught?: unknown,
  ): Promise<HumanStoryEvidence> {
    const failures = await visibleFailureText(this.page);
    const error =
      caught === undefined
        ? null
        : caught instanceof Error
          ? { name: caught.name, message: caught.message }
          : { name: "UnknownError", message: String(caught) };
    const evidence: HumanStoryEvidence = {
      schema_version: 1,
      story_id: this.storyId,
      title: this.title,
      viewport: { width: 1920, height: 1080 },
      video_size: { width: 1920, height: 1080 },
      started_at: this.#startedAt.toISOString(),
      duration_ms: Date.now() - this.#startedMs,
      outcome,
      error,
      events: this.#events,
      visible_failures: failures,
    };
    const evidenceDir = path.join(artifactRoot(), "evidence");
    await mkdir(evidenceDir, { recursive: true });
    await writeFile(
      path.join(evidenceDir, `${HUMAN_STORIES[this.storyId]}.json`),
      `${JSON.stringify(evidence, null, 2)}\n`,
      "utf8",
    );
    return evidence;
  }
}

export async function sendHumanChat(
  page: Page,
  recorder: HumanStoryRecorder,
  message: string,
  expectedPath?: string,
): Promise<string> {
  const finalized = page.locator(FINALIZED_ASSISTANT_SELECTOR);
  const before = await finalized.count();
  const composer = page.getByLabel("Message the buyer assistant", {
    exact: true,
  });
  recorder.record("user", { message });
  await composer.click();
  await composer.pressSequentially(message, { delay: 35 });
  const responsePromise = page.waitForResponse(
    (response) => isChatResponse(response),
    { timeout: CHAT_TIMEOUT_MS },
  );
  await composer.press("Enter");
  const response = await responsePromise;
  expect(response.ok(), "The live RouteDeck chat request must succeed.").toBe(
    true,
  );
  expect(response.headers()["content-type"]).toContain("text/event-stream");

  await expect
    .poll(
      async () => ({
        assistantCount: await finalized.count(),
        chatErrors: await page.locator(CHAT_ERROR_SELECTOR).count(),
        path: safePath(page.url()),
      }),
      { timeout: CHAT_TIMEOUT_MS },
    )
    .toEqual({
      assistantCount: before + 1,
      chatErrors: 0,
      path: expectedPath ?? safePath(page.url()),
    });

  const assistant = (await finalized.nth(before).innerText()).trim();
  recorder.record("assistant", { message: assistant });
  await page.waitForTimeout(1_200);
  return assistant;
}

export async function visibleCatalogProducts(
  page: Page,
): Promise<RenderedProduct[]> {
  const cards = page.locator("article[data-catalog-product]");
  const count = await cards.count();
  expect(count, "The live catalog must render at least one product.").toBeGreaterThan(
    0,
  );
  const products: RenderedProduct[] = [];
  for (let index = 0; index < count; index += 1) {
    const card = cards.nth(index);
    const handle = await card.getAttribute("data-catalog-product");
    const title = (await card.getByRole("link").innerText()).trim();
    if (handle === null || handle.length === 0 || title.length === 0) {
      throw new Error("A rendered product card is missing its public handle or title.");
    }
    products.push({ handle, title });
  }
  return products;
}

export async function openVisibleProduct(
  page: Page,
  recorder: HumanStoryRecorder,
  product: RenderedProduct,
): Promise<void> {
  const link = page.getByRole("link", { name: product.title, exact: true });
  await expect(link).toHaveCount(1);
  recorder.record("selection", {
    selection_kind: "product",
    title: product.title,
    handle: product.handle,
  });
  await link.click();
  await expect(
    page.getByRole("heading", { name: product.title, exact: true }),
  ).toBeVisible();
  await expectRouteDeckLive(page);
  await page.waitForTimeout(900);
}

export async function selectVisibleInStockVariant(
  page: Page,
  recorder: HumanStoryRecorder,
): Promise<RenderedVariant> {
  const group = page.getByRole("group", { name: "Choose a variant", exact: true });
  const radios = group.getByRole("radio");
  const count = await radios.count();
  for (let index = 0; index < count; index += 1) {
    const radio = radios.nth(index);
    if (!(await radio.isEnabled())) continue;
    const label = await radio.evaluate((element) =>
      (element.closest("label")?.innerText ?? "").replace(/\s+/g, " ").trim(),
    );
    const value = await radio.getAttribute("value");
    if (label.length === 0 || value === null || value.length === 0) {
      throw new Error("An enabled rendered variant is missing its label or value.");
    }
    recorder.record("selection", {
      selection_kind: "variant",
      label,
      value,
    });
    await radio.click();
    await expect(radio).toBeChecked();
    await expectRouteDeckLive(page);
    await page.waitForTimeout(700);
    return { label, value };
  }
  throw new Error("The rendered product has no enabled in-stock variant.");
}

export async function addSelectedVariant(page: Page): Promise<void> {
  const form = page.locator("form[data-catalog-add-to-cart]");
  const response = waitForSuccessfulPost(page, "/api/routedeck/dispatch");
  await page.getByRole("button", { name: "Add to cart", exact: true }).click();
  await response;
  await expect(form).toHaveAttribute("aria-busy", "false");
  await page.waitForTimeout(900);
}

export async function openCartFromSurface(page: Page): Promise<void> {
  const response = waitForSuccessfulPost(page, "/api/routedeck/dispatch");
  await page.getByRole("button", { name: "View cart", exact: true }).click();
  await response;
  await expect(
    page.getByRole("heading", { name: "Your cart", exact: true }),
  ).toBeVisible();
  await expectRouteDeckLive(page);
  await page.waitForTimeout(900);
}

export function humanBuyer(storyId: HumanStoryId): HumanBuyerProfile {
  if (storyId !== "US-05") {
    throw new Error("Only US-05 declares a checkout buyer fixture.");
  }
  return Object.freeze({
    email: "routedeck-human-story-05@example.test",
    firstName: "Test",
    lastName: "Story Five",
    address1: "5 Recorded Journey Street",
    city: "London",
    province: "Greater London",
    postalCode: "SW1A 1AA",
    countryLabel: "GB",
    phone: "+442079460005",
  });
}

export async function expectRouteDeckLive(page: Page): Promise<void> {
  await expect(
    page.getByRole("complementary", { name: "Navgraph", exact: true }),
  ).toHaveAttribute("data-status", "live");
}

export async function waitForSuccessfulPost(
  page: Page,
  pathname: string,
): Promise<Response> {
  const response = await page.waitForResponse((candidate) => {
    const request = candidate.request();
    return (
      request.method() === "POST" &&
      new URL(candidate.url()).pathname === pathname
    );
  });
  expect(response.ok(), `${pathname} must succeed.`).toBe(true);
  return response;
}

function isChatResponse(response: Response): boolean {
  return (
    response.request().method() === "POST" &&
    new URL(response.url()).pathname === CHAT_PATH
  );
}

async function visibleFailureText(page: Page): Promise<string[]> {
  const failures = page.locator(
    `${CHAT_ERROR_SELECTOR}, [role="alert"], [data-routedeck-error]`,
  );
  const count = await failures.count();
  const messages: string[] = [];
  for (let index = 0; index < count; index += 1) {
    const text = (await failures.nth(index).innerText()).trim();
    if (text.length > 0) messages.push(text);
  }
  return messages;
}

function artifactRoot(): string {
  const value = process.env.ROUTEDECK_HUMAN_STORY_ARTIFACTS;
  if (value === undefined || value.trim().length === 0) {
    throw new Error("ROUTEDECK_HUMAN_STORY_ARTIFACTS is required.");
  }
  return value;
}

function safePath(rawUrl: string): string {
  if (rawUrl.length === 0 || rawUrl === "about:blank") return rawUrl;
  return new URL(rawUrl).pathname;
}

function publicPathTemplate(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);
  if (
    segments.length === 5 &&
    segments[0] === "api" &&
    segments[1] === "routedeck" &&
    segments[2] === "reviews"
  ) {
    return `/api/routedeck/reviews/{review_id}/${segments[4]}`;
  }
  if (
    segments.length === 4 &&
    segments[0] === "api" &&
    segments[1] === "routedeck" &&
    segments[2] === "private-forms"
  ) {
    return "/api/routedeck/private-forms/{form_id}";
  }
  return pathname;
}
