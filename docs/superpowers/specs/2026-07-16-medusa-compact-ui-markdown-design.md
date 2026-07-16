# Medusa Compact UI And Markdown Design

Date: 2026-07-16
Status: approved visual direction; written-spec review pending
Runtime location: local Windows only

## Goal

Make the Medusa reference buyer UI more concise, professional, and polished
without changing its navigation, conversation, operation, review, checkout,
private-form, persistence, or deep-link behavior. Render buyer-assistant
Markdown as safe structured content instead of exposing Markdown punctuation.

The finished validation must include a fresh 1920x1080 live-model checkout
recording that visibly proves Navgraph state changes and both shareable and
session-bound deep links.

## Scope

The implementation may change:

- Medusa frontend presentation components under
  `examples/medusa-agent/frontend/src`;
- Medusa frontend CSS and visual tokens;
- the Medusa frontend package dependencies and workspace lockfile;
- targeted presentation tests and a test-only E2E recording probe.

The implementation must not change:

- RouteDeck or Medusa operation declarations, handlers, guards, providers, or
  transitions;
- canonical session, projection, review, private-form, or conversation state;
- chat, SSE, dispatch, navigation, or deep-link contracts;
- model configuration, buyer prompt, tool availability, Store API behavior, or
  checkout business rules;
- current labels used by accessibility and E2E contracts unless a visual-only
  wrapper can preserve their accessible names.

## Visual Direction

Use a compact professional workspace rather than a spacious marketing surface
or dense developer console.

### Palette

- Use a quiet cool-neutral canvas with true-white primary work surfaces.
- Retain Medusa coral as a restrained brand accent rather than a large ambient
  glow.
- Use deep sea green for interactive emphasis and current RouteDeck state.
- Use graphite text, neutral gray borders, and low-opacity shadows.
- Keep semantic success, warning, and error colors distinct and accessible.
- Remove decorative background gradients where they compete with content;
  subtle tonal variation may remain only where it helps separate workspace
  regions.

### Density And Geometry

- Reduce the application header to roughly 48-52 pixels.
- Reduce desktop workspace gutters and vertical gaps while preserving touch
  targets and keyboard focus visibility.
- Use a compact spacing scale centered on 4, 6, 8, 12, 16, and 24 pixels.
- Reduce message, surface, form, and checkout padding by roughly 20-30 percent.
- Prefer 8-12 pixel radii and restrained borders over large pill/card geometry.
- Keep the composer continuously usable without allowing it to dominate the
  viewport.
- Preserve the existing responsive layout and prevent horizontal overflow at
  narrow widths.

### Typography

- Use one disciplined system-sans family for interface and content text.
- Keep the Medusa wordmark distinctive through weight and tracking rather than
  mixing an unrelated display serif into application chrome.
- Use compact but readable line heights: approximately 1.35 for conversation
  content and 1.2-1.3 for headings and controls.
- Make message-role labels quieter and smaller than message content.
- Give controls explicit type size and weight; do not rely on browser defaults.

## Markdown Rendering

Use `react-markdown` with `remark-gfm` in the Medusa frontend.

- Render assistant content through a dedicated `AssistantMarkdown` component.
- Continue rendering buyer messages as literal text so buyer input is never
  reinterpreted as formatting.
- Disable raw HTML. Do not add `rehype-raw` or another HTML execution path.
- Support paragraphs, emphasis, strong text, ordered/unordered lists, links,
  inline code, fenced code, block quotes, and tables.
- Constrain generated links to safe protocols. External links open separately
  with `noopener noreferrer`; local links stay within the current browser
  context.
- Style Markdown elements through a scoped message-content class with compact
  margins and readable wrapping.
- Preserve streaming behavior: incomplete Markdown during a stream may render
  progressively but must not change conversation lifecycle or durable content.

## Component Changes

### Conversation

- Add the Markdown renderer as a focused presentation component.
- Keep message IDs, roles, statuses, streaming indicators, live-region
  semantics, and scrolling behavior unchanged.
- Use flatter message geometry, tighter spacing, and more deliberate maximum
  widths.

### Application Shell And Composer

- Tighten the header, workspace, message rail, suggested-action rail, and input
  dock.
- Preserve all existing buttons, accessible names, enabled/disabled states,
  retry/discard behavior, and keyboard submission.

### Commerce Surfaces

- Apply the same compact tokens to catalog, product, cart, contact, delivery,
  payment, review, and confirmation surfaces.
- Keep existing information hierarchy and operation wiring.
- Improve scanability with smaller section gaps, clearer dividers, aligned
  labels, and consistent control heights.

### Navgraph

- Keep the Navgraph read-only and preserve its current drawer, graph topology,
  focus, MiniMap, zoom, and current/reachable-state behavior.
- Restyle its chrome only as necessary to match the compact workspace.
- Ensure the open drawer remains legible at 1920x1080 while the buyer workflow
  remains usable beside it.

## Behavior Preservation

The UI remains a projection and control surface over the same RouteDeck
runtime. Chat and direct surface actions must continue to converge on the same
supervised operations. CSS changes and Markdown rendering must not create a
second state authority or bypass RouteDeck navigation.

No fixtures, scripted models, fallback responses, or deterministic product
stand-ins may enter the product path. The final recording uses the real local
Medusa stack and live buyer model.

## Verification

### Targeted Checks

- Add focused rendering tests for assistant Markdown, buyer literal text, raw
  HTML rejection, safe links, and streaming content.
- Run Medusa frontend typecheck and build.
- Run presentation tests immediately affected by Conversation, shell, catalog,
  cart, checkout, review, and Navgraph styling/component changes.
- Use the Browser integration first for desktop visual inspection, console
  health, interaction proof, and a narrow responsive check.

### Recorded Live E2E

Record one fresh Playwright Chromium video with:

- 1920x1080 viewport and video frame;
- live model and real local Medusa;
- one worker, zero retries;
- no direct browser calls to the Medusa Store API;
- the Navgraph drawer opened before meaningful navigation and kept visible
  during the principal transitions.

The recorded story must prove:

1. a fresh Home greeting and `buyer.home` as the current Navgraph node;
2. general buyer discovery followed by Catalog navigation and the corresponding
   current-node change;
3. a direct shareable product deep link, product resolution, matching Navgraph
   node, and successful reload;
4. product selection and cart navigation with visible current-node changes;
5. checkout contact and delivery progression;
6. a session-bound checkout deep link containing the active resume capability,
   successful reload, and preservation of the exact checkout state;
7. payment, review, explicit order approval, and confirmation;
8. a session-bound confirmation deep-link reload with the same confirmation
   handle and confirmation state;
9. no visible raw Markdown punctuation, tool serialization, framework overlay,
   relevant console error, unexpected HTTP failure, or direct browser-to-Medusa
   request.

If any required step fails, retain the video and report the exact stopping
point. Do not describe a partial flow as a passing checkout.

## Deliverables

- compact UI and Markdown implementation;
- targeted tests and verification output;
- one fresh 1920x1080 WebM recording;
- final confirmation screenshot and Playwright trace/report;
- concise findings covering Navgraph transitions, both deep-link classes,
  Markdown output, checkout completion, and any remaining visual or agent
  quality issues;
- a focused implementation commit after verification, with no push unless the
  user explicitly requests it.
