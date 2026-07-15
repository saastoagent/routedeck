# RouteDeck Human User-Story Video Assessment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record five realistic first-time RouteDeck Medusa shopper stories at 1920 x 1080, preserve one video and evidence record per story, and publish a findings report without repairing discovered product defects.

**Architecture:** A dedicated Playwright configuration isolates the assessment from ordinary regression projects and forces a 1920 x 1080 viewport and video encoder size. A focused story-support module derives product and variant choices from rendered surfaces, records chat and navigation evidence, and never retries model turns. A collector maps Playwright result attachments to stable artifact names, after which the final report classifies observed behavior without changing the product.

**Tech Stack:** TypeScript, Playwright 1.61.1, React-rendered RouteDeck surfaces, PowerShell, Docker Compose, live OpenAI-backed Medusa agent.

## Global Constraints

- Run locally on Windows; do not use a remote host.
- Use the approved SaaStoAgent STA key in memory only; never print or copy it.
- Do not reset or delete protected Medusa volumes.
- Do not perform Git operations.
- Do not modify product, prompt, model, or RouteDeck behavior in response to findings.
- Do not mock catalog, cart, checkout, order, or agent responses.
- Every story starts in a fresh browser context and buyer session.
- Record every story with viewport 1920 x 1080, video size 1920 x 1080, device scale factor 1, one worker, and zero retries.
- Preserve passing and failing videos.
- Only Story 5 may place an order.

---

### Task 1: Isolated Full-HD Playwright Configuration

**Files:**
- Create: `examples/medusa-agent/e2e/human-stories.playwright.config.ts`
- Modify: `examples/medusa-agent/e2e/package.json`

**Interfaces:**
- Consumes: `ROUTEDECK_E2E_BASE_URL`, `ROUTEDECK_MODEL_MODE`, and `ROUTEDECK_HUMAN_STORY_ARTIFACTS` environment variables.
- Produces: Playwright project `human-stories-1920x1080`, raw result videos, screenshots, traces, and `playwright-report.json`.

- [ ] **Step 1: Add an isolated configuration with exact capture dimensions**

```ts
import path from "node:path";
import { defineConfig } from "@playwright/test";

const artifactRoot = process.env.ROUTEDECK_HUMAN_STORY_ARTIFACTS;
if (artifactRoot === undefined || artifactRoot.trim().length === 0) {
  throw new Error("ROUTEDECK_HUMAN_STORY_ARTIFACTS is required.");
}

export default defineConfig({
  testDir: import.meta.dirname,
  outputDir: path.join(artifactRoot, "raw-results"),
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 360_000,
  expect: { timeout: 20_000 },
  reporter: [
    ["line"],
    ["json", { outputFile: path.join(artifactRoot, "playwright-report.json") }],
  ],
  use: {
    baseURL: process.env.ROUTEDECK_E2E_BASE_URL ?? "http://127.0.0.1:5198",
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    serviceWorkers: "block",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    video: { mode: "on", size: { width: 1920, height: 1080 } },
    screenshot: "on",
    trace: "on",
  },
  projects: [{ name: "human-stories-1920x1080", use: { browserName: "chromium" } }],
});
```

- [ ] **Step 2: Add one explicit package command**

```json
"test:human-stories": "playwright test human-user-stories.spec.ts --config human-stories.playwright.config.ts"
```

- [ ] **Step 3: Type-check the configuration only after Task 3 is present**

Run: `npm run typecheck` from `examples/medusa-agent/e2e`
Expected: exit 0 with no TypeScript diagnostics.

### Task 2: Human Story Evidence and Interaction Support

**Files:**
- Create: `examples/medusa-agent/e2e/support/human-story.ts`

**Interfaces:**
- Produces: `HumanStoryId`, `HumanStoryEvidence`, `createHumanStoryRecorder`, `sendHumanChat`, `visibleCatalogProducts`, `openVisibleProduct`, `selectVisibleInStockVariant`, `addSelectedVariant`, `openCartFromSurface`, and `humanBuyer`.
- Consumes: Playwright `Page`, `TestInfo`, the existing RouteDeck DOM contracts, and only rendered product/variant values.

- [ ] **Step 1: Define exact story identities and stable artifact names**

```ts
export const HUMAN_STORIES = {
  "US-01": "01-curious-newcomer",
  "US-02": "02-goal-led-discovery",
  "US-03": "03-changes-mind",
  "US-04": "04-hybrid-cart-management",
  "US-05": "05-thoughtful-checkout",
} as const;
export type HumanStoryId = keyof typeof HUMAN_STORIES;
```

- [ ] **Step 2: Record a sanitized event timeline**

The recorder must retain timestamps, route changes, user prompts, finalized assistant text, response status/path templates, console warnings/errors, visible failure text, selected rendered product title, selected rendered variant label, and final outcome. It writes `evidence/<stable-name>.json` in `finally`, even when an assertion throws. It must not record private form values or raw private identifiers.

```ts
export interface HumanStoryEvent {
  at_ms: number;
  kind: "route" | "user" | "assistant" | "network" | "console" | "selection" | "assertion";
  detail: Record<string, unknown>;
}

export interface HumanStoryEvidence {
  schema_version: 1;
  story_id: HumanStoryId;
  title: string;
  viewport: { width: 1920; height: 1080 };
  video_size: { width: 1920; height: 1080 };
  started_at: string;
  duration_ms: number;
  outcome: "passed" | "failed";
  error: null | { name: string; message: string };
  events: HumanStoryEvent[];
}
```

- [ ] **Step 3: Implement non-retrying human chat**

`sendHumanChat(page, recorder, message, expectedPath?)` must type with a 35 ms per-character delay, wait for one `POST /api/routedeck/chat`, require an SSE 2xx response, wait for exactly one additional finalized assistant message, fail on `[data-agent-chat-error]`, optionally verify the expected route, record the user and assistant text, and then pause 1,200 ms for video readability. It must issue the supplied message exactly once.

- [ ] **Step 4: Derive product and variant selections from rendered DOM**

`visibleCatalogProducts(page)` must inspect scoped `article[data-catalog-product]` elements, return their visible title and stable handle, and require at least two products for Story 3. `openVisibleProduct` must click a title returned by that function. `selectVisibleInStockVariant` must inspect enabled radios inside `fieldset` with legend `Choose a variant`, select a visible enabled option, and record its accessible label. No function may import `PRODUCT` from `support/test-data.ts`.

- [ ] **Step 5: Define isolated test-only buyers**

`humanBuyer(storyId)` returns explicit `example.test` addresses and `Test Story` postal identities for Story 5 only. The values are test fixtures isolated to E2E code and are never used as product data.

### Task 3: Five Independent Human User Stories

**Files:**
- Create: `examples/medusa-agent/e2e/human-user-stories.spec.ts`

**Interfaces:**
- Consumes: Task 2 helpers and existing checkout surfaces.
- Produces: five separately named Playwright results, one per approved story.

- [ ] **Step 1: Add shared safety guards and evidence finalization**

Each test must require `ROUTEDECK_MODEL_MODE === "live"`, require the exact local origin `http://127.0.0.1:5198`, verify `medusa-buyer-app`, capture a start screenshot, and wrap its story body so the recorder writes evidence on both pass and failure. Use the existing auto `browserSafety` fixture and call `assertClean()` at the end of a successful story.

- [ ] **Step 2: Implement US-01 Curious Newcomer**

Send exactly these first-time messages in order:

1. `Hey, I just landed here. What is this?`
2. `Okay, what can you actually help me do?`
3. `Cool. Show me what you have.`

Require finalized replies after each turn and require the final route `/products` with at least one rendered product. Do not click a product.

- [ ] **Step 3: Implement US-02 Goal-Led Discovery and Clarification**

Send `I'm after something comfortable for a relaxed weekend, but I'm not sure what. Can you help me narrow it down?`. If the assistant does not display the catalog, send one natural follow-up only: `Could you show me the available options?`. Choose a rendered product, open it, and ask `I can see the options for <rendered title> now. What should I consider when choosing between them?`. End on that product detail route with a finalized reply.

- [ ] **Step 4: Implement US-03 Shopper Changes Their Mind**

Send `I'm just browsing. Show me what's available.`, open one rendered product, then send `I'm not sure this is the one. Can I see the other products again?`. Require `/products`, open a different rendered product, select a visible in-stock variant, add it, open the cart, and prove the second rendered product is the only cart line.

- [ ] **Step 5: Implement US-04 Hybrid Cart Management**

Browse without naming a product, add a rendered product through surfaces, open the cart, increase quantity from 1 to 2, ask `What do I have in my cart right now?`, require the assistant answer not to visibly contradict the rendered title or quantity, decrease to 1, remove the item, require `Your cart is empty.`, then send `I'd like to keep looking. Take me back to the products.` and require `/products`.

- [ ] **Step 6: Implement US-05 Thoughtful Full Checkout**

Send `Can you help me find something simple and affordable?`, reach the catalog, open a rendered product, ask a clarification that mentions only the now-visible title, select a visible in-stock variant, add it, and send `This looks good. Can you take me to my cart?`. Complete the real private-form, delivery, payment, and review surfaces using the Story 5 test buyer. Stage the first review, reject it, prove no review acceptance request and no confirmation, stage a second distinct review, accept it once, verify confirmation, reload, and prove the same confirmation handle remains.

- [ ] **Step 7: Check only the new harness surface**

Run: `npm run typecheck`
Expected: exit 0.

Run: `$env:ROUTEDECK_HUMAN_STORY_ARTIFACTS='D:\Dev\AI Projects\routedeck\artifacts\routedeck-human-user-stories'; npx playwright test --config human-stories.playwright.config.ts --list`
Expected: exactly five tests in project `human-stories-1920x1080`.

### Task 4: Stable Video Collection and Assessment Manifest

**Files:**
- Create: `examples/medusa-agent/e2e/scripts/collect-human-story-artifacts.mjs`

**Interfaces:**
- Consumes: `playwright-report.json`, Playwright video attachments, and story evidence JSON files.
- Produces: stable `videos/*.webm` files and `assessment-manifest.json`.

- [ ] **Step 1: Parse the JSON report and copy each video**

The collector must map test titles beginning with `US-01` through `US-05` to the names in `HUMAN_STORIES`, require exactly one video attachment per attempted story, copy rather than move each attachment, and fail if any file is absent or empty.

- [ ] **Step 2: Write the manifest**

```json
{
  "schema_version": 1,
  "viewport": { "width": 1920, "height": 1080 },
  "video_size": { "width": 1920, "height": 1080 },
  "story_count": 5,
  "stories": []
}
```

Each story row must contain story ID, title, Playwright status, duration, stable video path, video byte count, video SHA-256, evidence path, evidence byte count, and evidence SHA-256. The collector fails unless it writes five rows and finds five non-empty videos and five non-empty evidence files.

- [ ] **Step 3: Run the collector after the live attempt**

Run: `node scripts/collect-human-story-artifacts.mjs "D:\Dev\AI Projects\routedeck\artifacts\routedeck-human-user-stories"`
Expected: exit 0 and `story_count: 5`.

### Task 5: Live Execution, Findings, and Completion Audit

**Files:**
- Create after execution: `artifacts/routedeck-human-user-stories/ROUTEDECK_HUMAN_USER_STORY_FINDINGS.md`
- Create during execution: `artifacts/routedeck-human-user-stories/videos/*.webm`
- Create during execution: `artifacts/routedeck-human-user-stories/evidence/*.json`
- Create during execution: `artifacts/routedeck-human-user-stories/assessment-manifest.json`

**Interfaces:**
- Consumes: Tasks 1-4, the protected local stack, and the approved STA key.
- Produces: the complete user-facing assessment.

- [ ] **Step 1: Start the protected local stack without resetting data**

Load `OPENAI_API_KEY` from the approved agent-core RouteDeck backend `.env` into the current process without printing it, then run:

`powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all`

Expected smoke URLs:

- `http://127.0.0.1:5198/`
- `http://127.0.0.1:8098/api/medusa-agent/health`
- `http://127.0.0.1:8098/api/medusa-agent/ready`
- `http://127.0.0.1:9100/health`

All must return HTTP 200, and ready must return `{"status":"ready"}`.

- [ ] **Step 2: Run the Browser-plugin preflight**

Use the in-app Browser runtime first. Verify page identity, meaningful DOM, no framework overlay, console health, one harmless browse interaction, and a 1920 x 1080 viewport. Finalize the preflight tab before the recorded run.

- [ ] **Step 3: Run the five stories once**

From `examples/medusa-agent/e2e`:

```powershell
$env:ROUTEDECK_MODEL_MODE='live'
$env:ROUTEDECK_E2E_BASE_URL='http://127.0.0.1:5198'
$env:ROUTEDECK_HUMAN_STORY_ARTIFACTS='D:\Dev\AI Projects\routedeck\artifacts\routedeck-human-user-stories'
npm run test:human-stories
```

Expected: five attempted stories with no retries. Product-story failures are retained as findings and are not rerun.

- [ ] **Step 4: Collect and verify artifacts**

Run the Task 4 collector. Verify five stable videos, five evidence files, SHA-256 values, and exact 1920 x 1080 configuration evidence. If local media tooling can inspect WebM dimensions, record that measurement; otherwise report the exact Playwright encoder configuration plus manifest evidence without claiming an independent codec probe.

- [ ] **Step 5: Write the findings report**

For every story, report outcome, duration, interaction timeline, model responses, surface transitions, errors, and links to video/evidence. Classify findings as critical, high, medium, low, or observation and distinguish product behavior, model behavior, harness behavior, and infrastructure. State explicitly that no product fixes were made.

- [ ] **Step 6: Stop only the Compose project and prove preservation**

Run:

`powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down`

Expected: zero project containers and all six protected volumes preserved.

- [ ] **Step 7: Audit every completion criterion**

Check the approved design against current artifacts: five attempted stories, five videos, five evidence files, 1920 x 1080 recording contract, final report, one-order maximum, no product fixes, local shutdown, and six protected volumes. Only after all evidence is present may the goal be marked complete.
