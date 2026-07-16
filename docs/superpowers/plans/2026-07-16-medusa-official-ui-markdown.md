# Medusa Official UI And Markdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the RouteDeck Medusa buyer experience a compact, professional UI based on Medusa's official design language, safely render assistant Markdown, and produce a real 1920x1080 checkout recording that proves Navgraph movement and both shareable and session-bound deep links.

**Architecture:** Keep every existing RouteDeck, Medusa, transport, and buyer-flow boundary unchanged. The changes stay inside the Medusa frontend presentation layer and its browser-test support: assistant text gains a dedicated safe renderer; the app receives product-scoped Medusa tokens, fonts, and mark; and the E2E observer asserts existing navigation state without owning it.

**Tech Stack:** React 19, TypeScript, CSS, `react-markdown@10.1.0`, `remark-gfm@4.0.1`, Inter and Roboto Mono from Fontsource, Vitest/Testing Library, Playwright.

## Global Constraints

- Do not change buyer-agent behavior, RouteDeck contracts, navigation ownership, Medusa business logic, accessible names, or test selectors.
- Render Markdown only for assistant messages. Buyer text remains literal text.
- Raw HTML stays disabled. External links must use a new tab with `noopener noreferrer`; local links stay in the current browsing context.
- Use real local Medusa and the real configured consumer agent for the final run. Do not add mock, fixture, canned, heuristic, or fallback product paths.
- Keep the Navgraph read-only. Observe current-node changes; never drive the product by clicking graph nodes.
- Keep tests proportional: run the new focused test after each implementation slice, then one frontend regression pass and one live checkout recording at the end.
- Preserve unrelated untracked Playwright outputs and do not push.

---

### Task 1: Add safe assistant Markdown rendering

**Files:**
- Modify: `examples/medusa-agent/frontend/package.json`
- Modify: `pnpm-lock.yaml`
- Create: `examples/medusa-agent/frontend/src/ui/AssistantMarkdown.tsx`
- Create: `examples/medusa-agent/frontend/src/tests/assistant-markdown.test.tsx`
- Modify: `examples/medusa-agent/frontend/src/ui/Conversation.tsx`

- [ ] **Step 1: Write focused renderer tests**

Cover headings, paragraphs, lists, tables, inline/fenced code, local links, external links, unsafe protocols, and literal raw HTML. Assert that external links receive `target="_blank" rel="noopener noreferrer"`, internal links do not, and no raw element is injected.

- [ ] **Step 2: Run the focused test and confirm it fails because the component is missing**

Run: `pnpm --filter @routedeck/medusa-agent exec vitest run src/tests/assistant-markdown.test.tsx`

- [ ] **Step 3: Install exact renderer dependencies and implement the component**

Add `react-markdown@10.1.0` and `remark-gfm@4.0.1`. Implement a presentation-only component with:

```tsx
import ReactMarkdown, { type Components, type UrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

const safeUrlTransform: UrlTransform = (url) => {
  const normalized = url.trim().toLowerCase();
  if (
    normalized.startsWith("javascript:") ||
    normalized.startsWith("vbscript:") ||
    normalized.startsWith("data:")
  ) {
    return "";
  }
  return url;
};

const components: Components = {
  a: ({ href = "", children, ...props }) => {
    const external = /^https?:\/\//i.test(href);
    return (
      <a
        {...props}
        href={href}
        target={external ? "_blank" : undefined}
        rel={external ? "noopener noreferrer" : undefined}
      >
        {children}
      </a>
    );
  },
};

export function AssistantMarkdown({ children }: { children: string }) {
  return (
    <div className="assistant-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={components}
        urlTransform={safeUrlTransform}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 4: Render assistant content through the new component**

Keep user messages as the existing literal `<p>{message.content}</p>`. Use `AssistantMarkdown` only when `message.role !== "user"`; preserve every message wrapper, role label, status marker, and data attribute.

- [ ] **Step 5: Run focused verification**

Run:

```powershell
pnpm --filter @routedeck/medusa-agent exec vitest run src/tests/assistant-markdown.test.tsx src/tests/app-shell.test.tsx
pnpm --filter @routedeck/medusa-agent typecheck
```

- [ ] **Step 6: Commit the passing slice**

Commit: `feat(medusa): render assistant markdown safely`

---

### Task 2: Add the official Medusa visual foundation

**Files:**
- Modify: `examples/medusa-agent/frontend/package.json`
- Modify: `pnpm-lock.yaml`
- Modify: `examples/medusa-agent/frontend/src/main.tsx`
- Create: `examples/medusa-agent/frontend/src/ui/MedusaMark.tsx`
- Modify: `examples/medusa-agent/frontend/src/ui/BuyerNavigation.tsx`
- Modify: `examples/medusa-agent/frontend/src/tests/app-shell.test.tsx`
- Modify: `examples/medusa-agent/frontend/src/app/app.css`

- [ ] **Step 1: Extend the shell test for the official brand mark**

Assert that the existing `Medusa Agent home` link retains its accessible name and contains the compact SVG mark without changing the visible `Medusa Agent` wordmark.

- [ ] **Step 2: Add local font packages**

Add exact dependencies `@fontsource-variable/inter@5.2.8` and `@fontsource/roboto-mono@5.2.9`. Import their CSS once in `main.tsx`; do not fetch runtime web fonts.

- [ ] **Step 3: Implement the official mark**

Create a decorative `MedusaMark` component using the official 64x64 path from the approved design specification, with `aria-hidden="true"`, `focusable="false"`, and `currentColor` so the enclosing link owns the accessible label.

- [ ] **Step 4: Replace the placeholder M badge**

Replace only `<span className="buyer-brand-mark">M</span>` with `MedusaMark`. Preserve navigation copy, hierarchy, destinations, controls, and accessible labels.

- [ ] **Step 5: Replace the global theme tokens**

Define the Medusa foundation in `app.css`:

```css
:root {
  font-family: "Inter Variable", Inter, ui-sans-serif, system-ui, sans-serif;
  color: #18181b;
  background: #ffffff;
  --medusa-bg-base: #ffffff;
  --medusa-bg-subtle: #fafafa;
  --medusa-bg-hover: #f4f4f5;
  --medusa-border-base: #e4e4e7;
  --medusa-border-strong: #d4d4d8;
  --medusa-fg-base: #18181b;
  --medusa-fg-subtle: #52525b;
  --medusa-fg-muted: #71717a;
  --medusa-bg-contrast: #18181b;
  --medusa-bg-contrast-hover: #27272a;
  --medusa-interactive: #3b82f6;
  --medusa-interactive-hover: #2563eb;
  --medusa-radius-control: 6px;
  --medusa-radius-card: 8px;
  --medusa-shadow-control: 0 1px 2px rgb(0 0 0 / 12%);
  --medusa-focus: 0 0 0 2px #ffffff, 0 0 0 4px rgb(59 130 246 / 45%);
}
```

Remove decorative green/coral gradients from the shell. Set a white canvas, 48-52px header, 14px/21px body typography, medium-weight headings, 13px controls, 6-8px radii, zinc rules, and blue only for interactive/focus states.

- [ ] **Step 6: Run shell verification**

Run:

```powershell
pnpm --filter @routedeck/medusa-agent exec vitest run src/tests/app-shell.test.tsx
pnpm --filter @routedeck/medusa-agent typecheck
```

---

### Task 3: Compact the conversation, surfaces, catalog, cart, and checkout

**Files:**
- Modify: `examples/medusa-agent/frontend/src/styles/conversation.css`
- Modify: `examples/medusa-agent/frontend/src/styles/surfaces.css`
- Modify: `examples/medusa-agent/frontend/src/styles/catalog.css`
- Modify: `examples/medusa-agent/frontend/src/styles/cart.css`
- Modify: `examples/medusa-agent/frontend/src/styles/checkout.css`
- Modify: `examples/medusa-agent/frontend/src/ui/navgraph-sidebar.css`

- [ ] **Step 1: Compact conversation and Markdown rhythm**

Use 4/6/8/12/16/24px spacing, flat white messages separated by subtle zinc rules, and restrained role labels. Style `.assistant-markdown` descendants without global element selectors: adjacent paragraphs, headings, lists, blockquotes, tables, code, preformatted blocks, and links. Ensure long code and tables scroll inside the message instead of widening the application.

- [ ] **Step 2: Restyle shared controls and fields**

Use 32-36px controls, 6px radii, white neutral buttons with the official outline/shadow, black primary buttons, blue focus rings, and compact form rows. Preserve disabled, pending, error, and selected distinctions without decorative gradients.

- [ ] **Step 3: Flatten commerce surfaces**

Restyle product, variant, cart, checkout, review, and confirmation surfaces to 8px cards, 1px zinc borders, minimal shadows, medium headings, muted metadata, and denser grids. Remove hover lift and Georgia/serif typography. Keep all responsive behavior and selectors intact.

- [ ] **Step 4: Restyle the Navgraph as an inspector**

Use a white panel with zinc dividers and compact facts. Product-scope graph nodes with CSS selectors for `data-node-tone`: blue current, zinc reachable/idle, no coral/green. Keep the drawer read-only, its open/close accessible names unchanged, and its live facts visible in the recording.

- [ ] **Step 5: Run presentation-adjacent tests once**

Run:

```powershell
pnpm --filter @routedeck/medusa-agent exec vitest run src/tests/app-shell.test.tsx src/tests/assistant-markdown.test.tsx src/tests/catalog-surface.test.tsx src/tests/cart-surface.test.tsx src/tests/checkout-surface.test.tsx src/tests/review-surface.test.tsx
pnpm --filter @routedeck/medusa-agent typecheck
```

- [ ] **Step 6: Commit the visual slice**

Commit: `style(medusa): align buyer UI with official design system`

---

### Task 4: Make the human checkout story prove Navgraph and deep links

**Files:**
- Modify: `examples/medusa-agent/e2e/human-checkout-flow.spec.ts`
- Modify: `examples/medusa-agent/e2e/support/buyer-flow.ts`
- Create: `examples/medusa-agent/live-checkout-video.playwright.config.ts`
- Modify: `examples/medusa-agent/package.json`

- [ ] **Step 1: Add observation-only helpers**

Add E2E helpers that open the Navgraph through its real UI control and assert exactly one node matching:

```ts
page.locator(`[data-routedeck-navgraph-node="${nodeId}"][data-node-tone="current"]`)
```

The helper must only inspect. It must not click a graph node or mutate navigation.

- [ ] **Step 2: Add optional stage observation to checkout support**

Extend `completeGuestCheckout` with an optional observer called after real stages become visible: contact, delivery, payment, review, approval, and confirmation. Keep its default behavior and existing callers unchanged. Use the observer only for assertions and reopening the drawer after a real reload.

- [ ] **Step 3: Rewrite the human story from genuine discovery**

Start with a curious buyer asking what the store offers. Clarify the available products, choose a product naturally, select a variant, change quantity/cart state, and proceed through guest checkout. Do not prime the agent with knowledge of a black tee or any hidden inventory assumption.

- [ ] **Step 4: Prove shareable product deep links**

From the real catalog response, extract the rendered product link, navigate directly to its actual href, assert the matching product surface and current Navgraph node, reload, and assert that both survive. Exercise browser back/forward as part of the visible story.

- [ ] **Step 5: Prove session-bound checkout and confirmation deep links**

At delivery, capture the actual URL and `resume_handle`, reload it, and assert the same stage and current node. At confirmation, capture and reload the actual confirmation URL and assert the same handle, confirmation content, and `orders.confirmation` current node.

- [ ] **Step 6: Add a dedicated 1920x1080 recording config**

Create a one-worker, zero-retry config targeting only the human checkout spec with:

```ts
use: {
  baseURL: "http://127.0.0.1:5198",
  viewport: { width: 1920, height: 1080 },
  video: "on",
  screenshot: "only-on-failure",
  trace: "retain-on-failure",
}
```

Require an absolute `ROUTEDECK_E2E_ARTIFACTS` directory outside the repository. Add a package script that invokes this config.

- [ ] **Step 7: Run E2E type-level discovery only**

Run: `pnpm --filter @routedeck/example-medusa-agent exec playwright test --config live-checkout-video.playwright.config.ts --list`

- [ ] **Step 8: Commit the E2E evidence harness**

Commit: `test(medusa): prove navgraph and checkout deep links`

---

### Task 5: Verify the implementation in the browser

**Files:**
- No product file changes expected.

- [ ] **Step 1: Verify local services and report their locations**

Verify:

```text
Frontend: http://127.0.0.1:5198/
Agent readiness: http://127.0.0.1:8098/api/medusa-agent/ready
Medusa health: http://127.0.0.1:9100/health
```

If any real dependency is unavailable, stop and report the blocker instead of substituting a fallback.

- [ ] **Step 2: Run final frontend checks**

Run:

```powershell
pnpm --filter @routedeck/medusa-agent test
pnpm --filter @routedeck/medusa-agent typecheck
pnpm --filter @routedeck/medusa-agent build
```

- [ ] **Step 3: Inspect the live page with the browser plugin**

At desktop 1920x1080, verify density, Markdown, no overflow, Navgraph clarity, and a direct deep-link reload. At 390px mobile width, verify no horizontal page overflow and usable composer/navigation controls. Inspect console and failed requests.

- [ ] **Step 4: Compare local screenshots**

Save the latest implementation screenshots outside the repo and inspect them at original resolution alongside the accepted official Medusa reference. Fix only confirmed visual defects within the approved presentation scope.

---

### Task 6: Record the real checkout and close the lane

**Files:**
- Store all recordings, screenshots, traces, and report output outside the repo.

- [ ] **Step 1: Record one real human-like checkout at 1920x1080**

Set a timestamped absolute `ROUTEDECK_E2E_ARTIFACTS` directory under the Codex visualization workspace and run:

```powershell
pnpm --filter @routedeck/example-medusa-agent test:human-checkout-video
```

The recording must visibly show fresh home, general discovery, Catalog, product deep-link reload, product/cart transitions, checkout stages, session-bound delivery reload, review, explicit approval, confirmation, confirmation reload, and the matching Navgraph current node throughout.

- [ ] **Step 2: Inspect the resulting video and evidence**

Confirm 1920x1080 metadata, nonzero duration, readable UI, complete story, no raw Markdown or serialized tool payloads, no stuck overlay, and no direct Medusa/network/console failure. Do not call the run passed based only on Playwright's exit code.

- [ ] **Step 3: Confirm repository state**

Verify the three implementation commits are present, unrelated untracked outputs remain untouched, and no unexpected product files or generated artifacts are staged.

- [ ] **Step 4: Deliver exact evidence**

Report the local runtime commands and URLs, targeted and final test results, commit IDs, absolute video/report paths, deep-link and Navgraph assertions, and any remaining defects. Cite Medusa's official site and documentation for the visual-source claims. Do not push.
