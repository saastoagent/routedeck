# RouteDeck Medusa Human User-Story Assessment

**Run date:** 2026-07-15
**Runtime:** Local Windows Docker Desktop
**Application:** RouteDeck Medusa reference application
**Assessment mode:** Live model, one worker, zero retries, no product fixes

## Executive Result

All five approved stories were attempted once and all five recordings were
preserved at an independently measured 1920 x 1080 resolution. None of the five
stories reached its complete acceptance endpoint:

- four stories were blocked by live conversational catalog navigation;
- one story reached the catalog and was then blocked by an assessment-harness
  locator defect;
- the checkout and order-review portion was not reached;
- no order was placed;
- no product, prompt, agent, or UI defects were fixed or rerun.

The strongest product finding is not merely that navigation was inconsistent.
Two sessions displayed internal-looking tool invocation data in the buyer chat.
The Story 5 output also contained corrupted and unsafe-looking foreign-language
text inside the apparent tool serialization.

## Environment and Commands

Protected stack startup:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all
```

The approved SaaStoAgent STA key was loaded from the existing agent-core
environment into process/container memory. It was not printed or copied into
RouteDeck.

Smoke URLs, all HTTP 200 before the run:

- `http://127.0.0.1:5198/`
- `http://127.0.0.1:8098/api/medusa-agent/health`
- `http://127.0.0.1:8098/api/medusa-agent/ready`
- `http://127.0.0.1:9100/health`

Readiness body: `{"status":"ready"}`

Focused harness checks:

- `npm run typecheck` -> passed
- `npx playwright test --config human-stories.playwright.config.ts --list`
  -> exactly five tests in one file

Recorded run:

```powershell
$env:ROUTEDECK_MODEL_MODE='live'
$env:ROUTEDECK_E2E_BASE_URL='http://127.0.0.1:5198'
$env:ROUTEDECK_HUMAN_STORY_ARTIFACTS='D:\Dev\AI Projects\routedeck\artifacts\routedeck-human-user-stories'
npm run test:human-stories
```

Result: `5 failed`; all five were attempted with one worker and zero retries.

## Recording Verification

The Playwright project set both viewport and encoder size to 1920 x 1080 with
device scale factor 1. Playwright's bundled FFmpeg independently read every
stable artifact as VP8, `1920x1080`, sample aspect ratio `1:1`, display aspect
ratio `16:9`, and `25 fps`.

| Story | Result | Test duration | Video duration | Size | Video |
|---|---:|---:|---:|---:|---|
| US-01 Curious Newcomer | Failed | 206.5 s | 02:52.16 | 10,071,705 bytes | [01-curious-newcomer.webm](videos/01-curious-newcomer.webm) |
| US-02 Goal-Led Discovery | Failed (harness) | 52.2 s | 00:48.00 | 2,964,449 bytes | [02-goal-led-discovery.webm](videos/02-goal-led-discovery.webm) |
| US-03 Changes Their Mind | Failed | 195.9 s | 02:36.92 | 7,294,910 bytes | [03-changes-mind.webm](videos/03-changes-mind.webm) |
| US-04 Hybrid Cart Management | Failed | 193.7 s | 02:37.64 | 7,236,830 bytes | [04-hybrid-cart-management.webm](videos/04-hybrid-cart-management.webm) |
| US-05 Thoughtful Checkout | Failed | 197.5 s | 02:44.12 | 9,012,862 bytes | [05-thoughtful-checkout.webm](videos/05-thoughtful-checkout.webm) |

Checksums and evidence measurements are in
[assessment-manifest.json](assessment-manifest.json).

## Findings

### F-01 High: Internal tool serialization leaked into buyer-visible chat

**Stories:** US-03 and US-05
**Category:** Product/model behavior
**Likely ownership:** live agent output normalization, turn policy, or SSE/chat
serialization; exact root cause was not diagnosed in this no-fix pass.

US-03 displayed this prefix in the finalized assistant message:

```text
{"type":"tool","name":"rd_catalog_list_23d687f9a05b","arguments":{}}
```

The route nevertheless remained `/`.

US-05 displayed a larger malformed block containing the tool name twice,
Markdown JSON fencing, serialization diagnostics, and the following unrelated
foreign-language phrase:

```text
日本不卡免费播放免费观看
```

The visible reply then claimed it would pull up options, but the route remained
`/`. This is a serious trust, safety, and product-quality failure even though
the chat HTTP response itself was 200 and no `[data-agent-chat-error]` appeared.

**Evidence:**

- [US-03 evidence](evidence/03-changes-mind.json)
- [US-03 video](videos/03-changes-mind.webm)
- [US-05 evidence](evidence/05-thoughtful-checkout.json)
- [US-05 video](videos/05-thoughtful-checkout.webm)
- the raw Playwright error-context snapshots under `raw-results/`

### F-02 High: Natural browse requests did not reliably open the catalog

**Stories:** US-01, US-03, US-04, and US-05
**Category:** Product/model behavior
**Likely ownership:** Medusa live-agent instruction grounding and turn/tool
policy.

Four independent fresh sessions finalized assistant replies but stayed at `/`
instead of reaching `/products`:

- US-01: `Cool. Show me what you have.`
- US-03: `I'm just browsing. Show me what's available.`
- US-04: `I'd like to browse before deciding. What do you have?`
- US-05 follow-up: `Show me the options so I can decide.`

All seven chat requests across these four sessions returned HTTP 200 SSE
responses. There were no visible chat-error components. US-03 and US-05 even
showed apparent catalog-tool syntax, yet no route transition occurred.

US-02 proves the operation can work: its second request, `Could you show me the
available options?`, reached `/products` and rendered the authoritative four
product catalog. The same high-level intent therefore behaves inconsistently
across fresh sessions.

### F-03 Medium: The assistant repeatedly invented catalog breadth and capabilities

**Stories:** US-01 through US-05
**Category:** Product/model grounding

Before reading the real catalog, assistant messages suggested unsupported or
irrelevant categories and filters, including skincare, snacks, supplements,
electronics, groceries, household basics, home products, phone accessories,
dietary needs, flavors, brands, and best sellers. The authoritative catalog in
this run contained only four Medusa apparel products at EUR 10.

US-01 also claimed it could filter by brand, price, dietary needs, and size and
could compare options end-to-end. Those claims were not grounded in the current
projected capabilities presented to the shopper.

This makes the first-time explanation misleading before the buyer has made any
choice.

### F-04 Medium: The Story 2 harness used visible text as an exact accessible name

**Story:** US-02
**Category:** Assessment harness

US-02 behaved best at the product level:

1. It asked useful clarification questions.
2. The natural follow-up navigated to `/products`.
3. The assistant accurately listed the four rendered products and EUR 10 price.

The assessment then derived the visible text `Medusa T-Shirt`, but attempted an
exact role lookup using that string. RouteDeck's link accessible name was
`Medusa T-Shirt ->`, so the harness found zero links and stopped before product
clarification.

This is not a product defect. It prevented Stories 2's deeper coverage. Per the
assessment instruction, the harness was not corrected and the story was not
rerun.

**Likely owner:** `examples/medusa-agent/e2e/support/human-story.ts`, rendered
product selection helper.

### F-05 Low: Failure evidence waits and transcript capture are too late

**Category:** Assessment harness

When a reply finalized but the expected route did not appear, the harness kept
the story open for the full 150-second route timeout. This makes four videos
longer than necessary after the actual failure is already visible.

The helper also records the assistant transcript only after both reply and route
expectations pass. Consequently, the failed-turn assistant text is present in
the video, screenshot, trace, and Playwright error-context snapshot, but not in
the compact story evidence JSON.

This did not erase the evidence, but it reduced report ergonomics. It was not
fixed or rerun.

### Observation: Fresh-session bootstrap emits an expected 404 resource message

Each Playwright story recorded one GET `/api/routedeck/session` HTTP 404 while
creating a new buyer session, plus a matching browser console resource message.
The existing browser-safety fixture explicitly classifies that session miss as
expected. No other HTTP failures or visible error components were recorded.

## Story-by-Story Findings

### US-01 Curious Newcomer

The assistant explained the site and its claimed capabilities, but used
irrelevant catalog examples. When explicitly asked to show available products,
it asked another category question instead of showing the catalog. The story
ended at `/` after three successful SSE turns.

Evidence: [JSON](evidence/01-curious-newcomer.json) ·
[video](videos/01-curious-newcomer.webm)

### US-02 Goal-Led Discovery and Clarification

The agent asked reasonable lifestyle/fit clarification questions. The follow-up
successfully displayed the real catalog and produced the most grounded answer
of the run. A harness accessible-name mismatch stopped the story before opening
the product. Product status beyond the catalog is therefore unassessed, not
failed.

Evidence: [JSON](evidence/02-goal-led-discovery.json) ·
[video](videos/02-goal-led-discovery.webm)

### US-03 Shopper Changes Their Mind

The first browse request exposed raw tool JSON in the assistant bubble and did
not open the catalog. The shopper never reached the first product, so the
change-of-mind and cart portions were not exercised.

Evidence: [JSON](evidence/03-changes-mind.json) ·
[video](videos/03-changes-mind.webm)

### US-04 Hybrid Cart Management

The assistant responded by asking for another category and budget rather than
showing the real catalog. No product, cart quantity, removal, or chat/surface
synchronization step was reached.

Evidence: [JSON](evidence/04-hybrid-cart-management.json) ·
[video](videos/04-hybrid-cart-management.webm)

### US-05 Thoughtful Full Checkout

The first reply again suggested unsupported categories and US-dollar budgets.
The one permitted natural follow-up exposed corrupted tool serialization and
unsafe-looking unrelated text while claiming it would show options. The route
stayed `/`. Catalog selection, private checkout, review rejection/new review,
placement, and confirmation persistence were not reached. No order was placed.

Evidence: [JSON](evidence/05-thoughtful-checkout.json) ·
[video](videos/05-thoughtful-checkout.webm)

## Coverage Boundaries

Proven in this assessment:

- five fresh sessions were created;
- all chat requests returned live 200 SSE responses;
- first-time replies and requested navigation were observed without model
  retries or prompt feeding;
- US-02 rendered the real four-product catalog;
- all five videos are readable Full HD recordings.

Not proven because the stories did not reach those stages:

- product-detail clarification;
- change-of-mind navigation after viewing a product;
- visible variant selection and add-to-cart;
- cart quantity/removal and conversational synchronization;
- private checkout;
- review rejection followed by a distinct review;
- order placement and confirmation persistence.

The earlier single scripted checkout result is not used to mark these new human
stories as passed.

## No-Fix Attestation

No product, prompt, model, RouteDeck runtime, Medusa binding, or UI behavior was
changed during or after this assessment. The only files added or changed were
the approved story documentation, assessment harness/configuration, collector,
and generated evidence/report artifacts. No Git operations were performed.
