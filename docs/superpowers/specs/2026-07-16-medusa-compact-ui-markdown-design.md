# Medusa Compact UI And Markdown Design

Date: 2026-07-16
Status: approved compact direction; official Medusa brand revision under review
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

## Official Medusa Design References

The visual system is grounded in the current official Medusa properties,
inspected on 2026-07-16:

- `https://medusajs.com/` for the public brand, Medusa mark, marketing layout,
  and compact header/control treatment;
- `https://docs.medusajs.com/` for documentation typography, grid structure,
  code treatment, and information density;
- `https://docs.medusajs.com/ui` for the official React design-system
  principles and component language;
- `https://docs.medusajs.com/ui/colors/overview` for the official semantic
  color-token families;
- the official Button, Heading, and Text component documentation for variants,
  sizing, typography, and compact-leading conventions.

Medusa UI describes itself as the React implementation of Medusa's design
system and emphasizes simple, composable components that preserve native HTML
behavior. RouteDeck's Medusa consumer should adopt that visual language without
replacing its existing semantic elements or RouteDeck interaction contracts.

## Visual Direction

Use a compact professional workspace rather than a spacious marketing surface
or dense developer console.

### Official Medusa Palette

Use the measured light-theme Medusa UI tokens rather than a custom commerce
palette:

- `--bg-base: #ffffff` for the primary page and work surfaces;
- `--bg-subtle` and `--bg-component: #fafafa` for secondary regions;
- `--bg-base-hover` and `--bg-component-hover: #f4f4f5` for neutral hover;
- `--bg-base-pressed` and disabled neutral borders: `#e4e4e7`;
- `--border-base: #e4e4e7` and `--border-strong: #d4d4d8`;
- `--fg-base: #18181b`, `--fg-subtle: #52525b`, and
  `--fg-muted: #71717a`;
- `--contrast-bg-base: #18181b`, `--contrast-bg-hover: #27272a`, and
  `--contrast-bg-pressed: #3f3f46` for primary inverted controls;
- `--fg-interactive: #3b82f6` with `#2563eb` hover and the official blue focus
  ring treatment;
- official rose danger, amber/orange warning, emerald success, and neutral tag
  families only for matching semantic states.

The buyer application is therefore predominantly white, black, and zinc—not
coral or green. Remove the existing coral/green ambient gradients and decorative
color washes. Color is semantic or interactive, never decorative filler.

Use the official Medusa monochrome mark from `medusajs.com` in application
chrome: the black hexagonal-ring glyph with its circular center, rendered as an
inline accessible SVG at an optically balanced compact size. Keep the adjacent
`Medusa Agent` name and RouteDeck ownership copy as code-native text.

### Density And Geometry

- Reduce the application header to roughly 48-52 pixels.
- Reduce desktop workspace gutters and vertical gaps while preserving touch
  targets and keyboard focus visibility.
- Use a compact spacing scale centered on 4, 6, 8, 12, 16, and 24 pixels.
- Reduce message, surface, form, and checkout padding by roughly 20-30 percent.
- Use Medusa's 6-pixel radius for buttons and compact controls, and 8 pixels for
  code blocks, messages, containers, and larger surfaces. Avoid oversized
  pill/card geometry.
- Use Medusa's neutral button elevation (`0 1px 2px rgba(0,0,0,.12)` plus a
  subtle 1-pixel outline) and card elevation only where separation requires it.
- Prefer the official grid language: thin zinc rules, aligned columns, flat
  surfaces, and whitespace used for hierarchy instead of floating cards.
- Keep the composer continuously usable without allowing it to dominate the
  viewport.
- Preserve the existing responsive layout and prevent horizontal overflow at
  narrow widths.

### Official Medusa Typography

- Use Inter for headings, body, controls, labels, conversation, and commerce
  surfaces. Bundle the font locally so the local demo does not depend on a
  third-party font request.
- Use Roboto Mono for operation IDs, routes, Navgraph identifiers, code, and
  other technical tokens. Bundle it locally for the same reason.
- Match the measured public-site baseline: 14-pixel body text with a 21-22
  pixel line height, 13-pixel controls at weight 500, and headings at weight
  500 rather than heavy display weights.
- Use compact text leading where the official Text component language calls for
  it, while keeping assistant prose around 1.45 for readability.
- Keep role labels and metadata at 11-12 pixels in muted zinc.
- Remove the current Georgia display treatment from the application wordmark
  and confirmation heading.
- Use slightly negative tracking only for large headings; normal tracking for
  body and controls.

### Official Component Language

- Buttons use Medusa's primary inverted, secondary neutral, transparent, and
  danger hierarchy rather than bespoke green/coral variants.
- Fields use true-white or `#fafafa` backgrounds, zinc borders, 6-pixel radii,
  compact padding, and the official blue focus treatment.
- Containers remain simple and composable, following Medusa UI's native-HTML
  bias. Do not introduce a new wrapper component where existing semantic HTML
  already provides the correct behavior.
- Use the official monochrome icon/line language for navigation and status
  controls. Keep icon use sparse and functional.
- Code and technical details use dark zinc contrast surfaces or restrained
  zinc inline-code treatments modeled on Medusa Docs.

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
