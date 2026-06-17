# Medusa Agent Product Design QA

final result: passed

## Visual Target

Selected direction: Atelier Chat.

Reference image:

`C:\Users\ragha\.codex\generated_images\019e9ce9-6950-7ba0-9745-468096f0a059\ig_0295669bbfce7bb6016a2a7b4f6dec8191a1750af543c1f2dc.png`

## Reviewed Implementation

Local URL:

`http://127.0.0.1:5198/`

Additional state:

`http://127.0.0.1:5198/browse?surface_id=browse.product_list`

Browser capture:

- `design-qa-artifacts/medusa-browse-medusa-store-api-desktop.png`

## Correction Note

Prior QA notes incorrectly passed drifted states.

The first drifted version still had a marketing-style hero, generic branding,
and a branched route map that did not match the selected Atelier Chat direction.

The second drifted version removed the hero, but still promoted the browse
projection as a labeled RouteDeck surface in the central chat and used local
generated product images. That was invalid for Medusa Agent: product facts,
prices, and media must come from the read-only Medusa Store API or the UI must
show catalog unavailable. A fake catalog or local product media fallback is not
allowed in runtime.

This pass reviews the corrected implementation after replacing local product
media and static catalog assumptions with Store API-backed projection data.

## Checks

- Chat remains the primary product surface.
- The first screen starts with a compact assistant chat bubble, not a marketing hero.
- Home state does not show a RouteDeck/home surface card in the chat stream.
- Product projection is embedded in the conversation area as an assistant transcript turn.
- Browse state shows current Medusa Store API products as a compact comparison attachment.
- Product images come from projected Store API media URLs with `data-image-source="medusa_store_api"`.
- Local product image assets are not used for catalog products.
- Local brand art is allowed only under `/medusa-brand/*`; `/medusa-products/*`
  must not appear in runtime source or DOM.
- If Store API config or catalog read fails, the surface must show catalog unavailable instead of fake products.
- Central chat does not show RouteDeck implementation labels such as `Projected product surface`, `Browse projected products`, or `Read-only browse surface`.
- The projected surface scrolls above the composer and does not hide behind it.
- RouteDeck graph remains a literal graph view: `@xyflow/react` renders selectable nodes, with a deterministic visible spine as edge fallback.
- Route map is vertical: Home -> Browse -> Detail -> Cart.
- RouteDeck graph controls are not exposed as product actions.
- Inspector is secondary to the chat surface.
- Debug context is collapsed by default and remains temporary proof instrumentation.
- Composer remains visible at the tested desktop viewport.
- Product URL uses path plus optional `surface_id` query state.
- No new product writes, cart mutation, checkout, admin, or public `/api/routedeck/*` surface was added.

## Live Projection Evidence

Direct backend projection request:

`GET http://127.0.0.1:8098/api/medusa-agent/projection?path=/browse&surface_id=browse.product_list`

- HTTP status: `200`.
- Catalog status: `ok=true`, `source=medusa_store_api`, `code=medusa_catalog_loaded`, `count=4`, `priced=true`.
- Products: `Medusa T-Shirt`, `Medusa Sweatshirt`, `Medusa Sweatpants`, `Medusa Shorts`.
- Prices: `EUR 10.00` for all four returned Store API products.
- Product image source: `medusa_store_api`.
- Product image URLs: Medusa public S3 URLs under `https://medusa-public-images.s3.eu-west-1.amazonaws.com/`.
- Local catalog asset references: `false`.
- Detail node URL: `/detail/t-shirt`, derived from the first real Store API product in the current catalog snapshot.

## Browser Evidence

Latest live viewport: `1280 x 720`.

Browse URL:

- Product cards: `4`.
- Product names: `Medusa T-Shirt`, `Medusa Sweatshirt`, `Medusa Sweatpants`, `Medusa Shorts`.
- Product prices: `EUR 10.00`, `EUR 10.00`, `EUR 10.00`, `EUR 10.00`.
- Product image source markers: `medusa_store_api`, `medusa_store_api`, `medusa_store_api`, `medusa_store_api`.
- Local product image assets: `false`.
- Runtime `/medusa-products/*` references in DOM: `false`.
- Brand image path: `/medusa-brand/medusa-mark.png`.
- Dynamic chips: `Show products`, `Compare visible products`, `Sizing help`.
- Route graph nodes: `4`.
- React Flow edge paths: `3`.
- Visible route spine edges: `3`.
- Composer visible: `true`.
- Body scroll height equals viewport height: `720`.

Live chip behavior from `/`:

- Initial root chip: `Show me products`.
- Clicking the chip sent the chat prompt `Show me products in the current Medusa catalog`.
- Browser URL moved to `/browse?surface_id=browse.product_list`.
- Product cards rendered: `4`.
- Route graph retained: `4` nodes and `3` edges.
- Product image sources stayed `medusa_store_api`.
- Latest assistant answer listed the four Store API products with Store API-derived prices.

## Automated Evidence

- From `examples/medusa-agent/backend`: `python -m pytest tests/test_medusa_catalog.py tests/test_slice1_chat.py tests/test_slice2_projection.py tests/test_slice3_projection_surfaces.py -q`: `27 passed`.
- From `examples/medusa-agent/frontend`: `npm test -- --run`: `17 passed`.
- From `agent-lab-powered-projects/routedeck`: `python -m pytest tests/test_anti_drift_boundaries.py tests/test_medusa_reference_slice0.py -q`: `24 passed`.
- From `examples/medusa-agent/frontend`: `npx vite build`: passed.

Build note: Vite still warns that local Node.js `22.9.0` is below the preferred
`22.12+` line.

## Independent Drift Review

Initial fresh subagent verdict: `FAIL`, because docs/tests still contradicted
the Store API requirement and `/medusa-products/*` remained a path loophole for
brand media. Those blockers were patched.

Fresh subagent re-review verdict: `PASS`, with no remaining blockers for the
reported drift issues.

## Remaining Polish Notes

- P3: The browse projection now includes four products, so the chat pane scrolls
  to keep the latest projected turn and composer visible at a 1280 x 720
  viewport.
- P3: The collapsed debug context card remains temporary proof instrumentation
  and should be removed before the public example is final.
