# RouteDeck Human User-Story Video Assessment

**Date:** 2026-07-15
**Status:** Approved design awaiting written-spec review
**Target:** Local RouteDeck Medusa reference application

## Purpose

Assess the current RouteDeck Medusa experience through realistic first-time
shopper journeys. The assessment produces one readable video and one evidence
record per story, followed by a findings report. It does not repair product,
prompt, agent, or UI defects discovered during the run.

## Assessment Boundary

- Run the protected Medusa stack locally on Windows.
- Use the existing SaaStoAgent STA OpenAI key from the approved agent-core
  environment without copying or printing it.
- Start every story with a fresh browser context and buyer session.
- Exercise real Medusa catalog, cart, checkout, and order state.
- Use live model behavior. Do not inject, mock, retry, rewrite, or replace model
  responses to make a story pass.
- Do not reset or delete protected Medusa volumes.
- Do not modify product behavior during the assessment.
- Do not perform Git operations.

## Recording Contract

- Produce one separate WebM file for every story.
- Record at an explicit 1920 x 1080 video size and 1920 x 1080 browser
  viewport, with device scale factor 1.
- Do not use Playwright's default reduced video size.
- Type chat messages at a readable human pace.
- Pause on meaningful assistant replies and surface transitions long enough for
  a viewer to understand them.
- Keep the full application visible; avoid cramped mobile or split-screen
  layouts.
- Preserve videos for passing and failing stories.

## Human-Behavior Rules

- No user prompt may name a product, variant, colour, size, price, or other
  catalog fact before that information has appeared in the current story.
- A product may be mentioned only after the catalog or product surface makes it
  visible to the user.
- Product and variant choices must be derived from the current rendered
  surface, not from the test fixture constants.
- Chat and direct surface interactions must be mixed where the story calls for
  them.
- A model response that does not support the next natural action is a finding,
  not a reason to feed the agent a more convenient prompt.
- A product or runtime defect remains unfixed and is reported with its video.

## Story 1: Curious Newcomer

**Persona:** A visitor who does not yet understand the site.
**Goal:** Learn what the experience is before deciding whether to shop.

Journey:

1. Land on the welcome screen and read the greeting.
2. Ask what the site is.
3. Ask what the assistant can actually help with.
4. Ask to see what is available, without naming a product.
5. End on the rendered product catalog.

Acceptance evidence:

- The first two questions receive finalized assistant replies without forcing a
  catalog choice.
- The final request reaches a real catalog surface containing visible products.
- No visible chat failure, framework overlay, or relevant console error occurs.

## Story 2: Goal-Led Discovery and Clarification

**Persona:** A shopper with a broad lifestyle need but no chosen item.
**Goal:** Discover suitable options and understand one visible product.

Journey:

1. Describe a broad need such as comfortable clothing for a relaxed weekend.
2. Ask the assistant for help narrowing the choice.
3. Ask to see the available options if they are not already visible.
4. Choose a product only after its card is visible.
5. Ask a clarification based only on information now visible, such as available
   options, price, or intended use.
6. End on the product detail surface with a finalized reply.

Acceptance evidence:

- The assistant handles an open-ended need without requiring a preselected SKU.
- The selected product comes from the live rendered catalog.
- The clarification receives a finalized, non-error response grounded in the
  current interaction state.

## Story 3: Shopper Changes Their Mind

**Persona:** A browser who investigates one option, rejects it, and chooses
another.
**Goal:** Verify that chat, navigation, and surfaces remain coherent when intent
changes.

Journey:

1. Ask to browse without naming a product.
2. Open one visible product through the surface.
3. Tell the assistant the shopper is unsure and wants to see the other products
   again.
4. From the returned catalog, open a different visible product.
5. Select a currently visible variant and add it to the cart.
6. End with the second product present in the real cart.

Acceptance evidence:

- Chat-driven return to the catalog succeeds or is recorded as a failure.
- The second product differs from the first and is selected from rendered data.
- The cart reflects the second product and selected variant.

## Story 4: Hybrid Cart Management

**Persona:** A shopper who alternates between direct controls and conversational
help.
**Goal:** Verify that cart state and assistant context stay synchronized.

Journey:

1. Browse and add a visible product through rendered surfaces.
2. Open the cart and increase the line quantity using the cart controls.
3. Ask the assistant what is currently in the cart.
4. Decrease the quantity again using the surface.
5. Remove the item.
6. Ask to continue looking and end on the catalog.

Acceptance evidence:

- Quantity changes update the authoritative cart surface.
- The assistant's cart answer does not contradict the rendered cart state.
- Removal produces an empty cart.
- Conversational continuation returns to the catalog without hidden fallback
  behavior.

## Story 5: Thoughtful Full Checkout

**Persona:** A cautious shopper who discovers an item, verifies it, and reviews
the purchase before committing.
**Goal:** Exercise the complete conversational, surface, private-form, review,
and confirmation journey.

Journey:

1. Begin with a broad request for something simple and affordable.
2. Browse the real catalog and open a visible product.
3. Ask a clarification derived from the product surface.
4. Select a visible variant and add it to the cart.
5. Ask the assistant to open the cart.
6. Enter the guest contact and delivery information through the private form.
7. Select delivery and payment through their surfaces.
8. Review the order and request placement approval.
9. Cancel placement once to represent hesitation.
10. Stage a new placement review with a new review ID, reread the order, and
    explicitly place it. The rejected review is terminal and must never be
    reused.
11. Reload the confirmation route and verify the same confirmation persists.

Acceptance evidence:

- Chat and surface navigation operate on one buyer session and real cart.
- Private values remain within the private checkout channel.
- Cancellation does not place an order.
- Cancellation resolves only the first review; the later placement attempt
  produces a distinct review ID.
- Exactly one explicit final acceptance request places exactly one order.
- The confirmation survives reload with the same confirmation handle.

## Harness and Isolation Design

- Add a dedicated Playwright project for the five recorded stories rather than
  changing ordinary regression projects.
- Run the stories serially with one worker and no retries.
- Give each story its own browser context and distinct buyer identity.
- Keep the live-mode and exact-local-origin safety guards.
- Derive selectable products and variants from scoped rendered locators.
- Record story-level timing, current URL transitions, finalized chat text,
  relevant RouteDeck response statuses, console warnings/errors, and visible
  failure text.
- A story assertion may fail, but teardown must still preserve its video and
  evidence record.
- An infrastructure failure before the story begins is reported separately from
  a product-story failure. Stories are not silently rerun.

## Artifact Layout

Store the final assessment under:

`artifacts/routedeck-human-user-stories/`

- `videos/01-curious-newcomer.webm`
- `videos/02-goal-led-discovery.webm`
- `videos/03-changes-mind.webm`
- `videos/04-hybrid-cart-management.webm`
- `videos/05-thoughtful-checkout.webm`
- `evidence/<story>.json`
- `screenshots/<story>-<stage>.png` when a screenshot materially supports a
  finding
- `ROUTEDECK_HUMAN_USER_STORY_FINDINGS.md`

## Findings Report

The final report must contain:

- runtime location, startup command, smoke-test URLs, and recording command;
- a pass/fail result and duration for each story;
- a concise transcript and interaction timeline for each story;
- links to all five videos and supporting evidence;
- findings ranked as critical, high, medium, low, or observation;
- exact visible behavior, reproduction point, evidence, and likely ownership;
- explicit separation of product failures, model-behavior weaknesses,
  recording/harness defects, and infrastructure failures;
- confirmation that no product fixes were made;
- protected-stack shutdown and volume-preservation proof.

## Completion Criteria

The assessment is complete only when all five stories have been attempted, all
five videos have been preserved at 1920 x 1080, story evidence has been saved,
the findings report has been written, and the local stack has been stopped while
all protected volumes remain.
