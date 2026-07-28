# RouteDeck Wiki Reader

This private Vite/React workspace renders the checked-in Markdown under
`../wiki/`. It is a local reading surface, not a second documentation source
and not a framework runtime package.

From the repository root:

```powershell
pnpm install
pnpm wiki:dev
```

Open `http://127.0.0.1:5176/?page=Home`.

The reader provides grouped navigation, full-text search, URL-addressable
pages, an on-page outline, previous/next links, and a responsive mobile menu.
Markdown links between wiki pages remain inside the reader.

Mermaid blocks render client-side as responsive SVG diagrams. The reader pins
[`mermaid` 11.16.0](https://github.com/mermaid-js/mermaid) (MIT), loads it only
when a page contains a Mermaid block, and initializes it with
`securityLevel: "strict"` and `startOnLoad: false`. Checked-in Mermaid source
remains available through the disclosure below each diagram. A rendering error
is visible and preserves the original source; it never masquerades as a
successful diagram.

## Validation

```powershell
pnpm wiki:test
pnpm --filter @routedeck/wiki-site typecheck
pnpm wiki:build
```

The focused tests cover successful strict rendering and explicit render
failure in addition to navigation, search, and the page outline. Browser
verification should exercise at least one flowchart, sequence diagram, and
state diagram at desktop and mobile widths.

The canonical framework contract remains `../docs/route-deck-reference.md`.
The reader must not introduce contract text that is absent from `../wiki/`.
