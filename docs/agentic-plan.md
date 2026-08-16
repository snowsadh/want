# OpenAI Agentic Workflow Plan

> Implemented hackathon MVP workflow. Provider gate passed 2026-08-16.

## Decision

Use OpenAI for outfit inventory and live product discovery. Keep YouCam Clothes
V3 as the mandatory, visible try-on centerpiece.

```text
reference image
    -> OpenAI inventory of every distinct visible wearable
    -> local schema, pair and duplicate checks + item crops
    -> one concurrent OpenAI shopping request per item
    -> 0–3 ranked products per item
    -> default or user-selected product
    -> YouCam: full body -> shoes
       OR upper body -> lower body -> shoes
    -> final image + product links for every detected item
```

The MVP does **not** add a second verification call, HTTP link checker, image
download/cache/proxy, product database, provider toggle or background workflow.
If OpenAI finds no credible product, the original crop remains as an unlinked
reference.

## OpenAI requests

Use the installed `openai` client directly with `AsyncOpenAI` and the Responses
API for both stages:

```text
model:             gpt-5.6-terra
reasoning effort:  medium
text verbosity:    low
store:             false
service tier:      default
```

Inventory uses one `detail: original` image and structured output. Shopping uses
structured output plus hosted image and text web search. The official guidance
recommends original detail for small-object detection and localization:
[Images and vision](https://developers.openai.com/api/docs/guides/images-vision#choose-an-image-detail-level).
Image-search results include canonical `image_url` values in the same response:
[Image search results](https://developers.openai.com/api/docs/guides/tools-web-search#image-search-results).

Use the raw Responses client because the current Agents SDK wrapper does not
expose the image-search fields. Do not add another SDK or provider.

## Stage 1 — outfit inventory

Send the full reference once with the following prompt and structured schema.
There is no search or correction turn in this stage.

### Final inventory prompt

```text
Identify every distinct, separately shoppable item visibly worn by the main
person in the supplied reference image.

Include garments, footwear, legwear, bags, belts, scarves, hats, headbands,
substantial hair accessories and clearly visible statement jewelry. Ignore
tiny or barely visible jewelry, tiny decorative clips and non-wearable objects.

Return each visible item exactly once.

Rules:
- Do not invent hidden items or visually unsupported attributes.
- Treat a matching left/right pair of shoes, socks or leg warmers as one item.
- Keep separately shoppable overlapping layers as separate items.
- Do not create a separate item from only a small visible edge of an underlayer.
- Clothing tied around the waist remains that garment; do not relabel its
  sleeves or panels as a belt, sash or tie.
- Call an item a dress, romper or jumpsuit only when continuous construction
  across the waist is visible. Otherwise keep coordinated separates distinct.
- Use a tight [ymin, xmin, ymax, xmax] box normalized to 0..1000 for every item.
- Record only visible category, colors, silhouette, material appearance,
  pattern, print or graphic, construction and distinctive details.
- Use "unknown" when an attribute is not visually supported. Do not guess a
  brand, exact fabric composition or hidden construction.
- Mark an item partial or heavily occluded when its important shape is blocked
  or cut off.

Return only the structured inventory.
```

### Inventory schema

Reuse the current `LookAnalysis.garments` collection name to avoid a cosmetic
repository-wide rename; each row can represent any wearable item, including an
accessory.

```json
{
  "garments": [
    {
      "item_id": "upper_1",
      "body_slot": "upper_body | lower_body | full_body | shoes | accessory",
      "category": "cropped t-shirt",
      "box_2d": [200, 260, 420, 820],
      "visibility": "clear | partial | heavily_occluded",
      "visible_fraction": 1.0,
      "colors": ["pale yellow", "black"],
      "silhouette": "fitted cropped crew-neck tee",
      "material_appearance": "matte jersey-like knit",
      "pattern": "all-over line-art pattern",
      "print_or_graphic": "repeating abstract faces",
      "details": ["short sleeves", "crew neck"]
    }
  ]
}
```

All fields are required; lists may be empty. Boxes contain four integers in
`0..1000` with positive area, visible fraction is in `0..1`, and item IDs are
unique within the response. Do not ask the model for search queries, completion
items, scores, palette prose or application context.

## Stage 2 — local checks and crops

Perform one fast local pass:

1. Validate the structured result and box geometry.
2. Merge a left/right pair only when category and core visible attributes match.
3. Remove a likely duplicate only when body slot and category match, boxes
   strongly overlap, and core visible attributes agree.
4. Never merge different categories or separately declared layers.
5. Create one padded crop per remaining item.

The shopper receives both the crop and full reference because a tight crop can
omit a sleeve, hem or overlapping layer. These checks make no network requests.
Retry once only when the provider response cannot satisfy the schema.

## Stage 3 — concurrent item shopping

Make `LookBuilder.build()` async and await it from `POST /api/looks`. Fan out one
Responses request per normalized item with an `asyncio` semaphore capped at
eight. Isolate item errors so one failure becomes that item's crop fallback
instead of cancelling the look.

Each request receives only:

```text
TARGET ITEM       structured JSON for this item
TARGET CROP       original-resolution item crop
FULL REFERENCE    original image for category/layering ambiguity
```

### Web-search configuration

```json
{
  "type": "web_search",
  "search_context_size": "low",
  "search_content_types": ["image", "text"],
  "image_settings": {"max_results": 10, "caption": true}
}
```

Also cap hosted search calls:

```json
{
  "max_tool_calls": 3
}
```

The runtime consumes the selected structured `image_url`; it does not request or
parse raw search-result payloads, fetch the image, or run another validation pass.

### Final shopping prompt

```text
Find up to three closest currently buyable new-retail matches for the supplied
item.

Use the target crop to inspect the item. Use the full reference to resolve crop,
layering or category ambiguity. The structured item fields are visual notes;
the supplied images remain the evidence.

The product category must match. Search for the identical product first. If it
is unavailable, rank alternatives by:

1. color and style/silhouette;
2. design and pattern layout;
3. print or exact graphic;
4. material, texture and smaller details.

Relax lower-priority details before higher-priority details. When a graphic or
pattern covers most of an item, its scale and placement are part of the style,
not a minor keyword match.

Search using both image and text results. Choose the strongest attribute-rich
query first. Judge products from their images and product pages, not titles or
shared keywords alone.

Every returned product must:
- be the same product category as the target;
- be a distinct, currently buyable new-retail product;
- have a direct product-page URL;
- have a product image URL showing the matching product and color variant;
- have a listed price and currency, or null when genuinely unavailable.

Exclude resale and second-hand products, category or search-result pages,
editorial or inspiration pages, products whose image does not show the item,
and invented URLs, images, prices or availability.

When equally useful images exist for the same product, prefer one showing a
model wearing the item only when the target item is clearly isolated and other
clothing will not confuse virtual try-on. Otherwise prefer the clean product
image. This is a preference, not a requirement.

Use at most three web-search tool calls. Stop when three credible candidates
have been found. Return zero, one or two products rather than adding weak
matches. Order products from closest visual match to least close.

Return only the structured result.
```

A candidate is credible only when its category matches, its image shows the
linked product and color variant, its defining visual attributes are close, and
it has no major conflict that makes the outfit read as a different design.
Give up rather than returning a broad aesthetic or keyword-only match.

### Shopping schema

```json
{
  "item_id": "upper_1",
  "search_queries": ["query actually used"],
  "products": [
    {
      "match_kind": "exact | similar",
      "title": "product title",
      "retailer": "retailer name",
      "product_url": "https://retailer.example/product",
      "image_url": "https://cdn.example/product.jpg",
      "listed_price": 29.0,
      "listed_currency": "USD"
    }
  ],
  "give_up_reason": null
}
```

`products` has a hard maximum of three and its order is its rank. Product and
image URLs are required for every product. Price and currency are both values
or both null. `give_up_reason` is required only when products is empty. Keep
queries for benchmark diagnostics; do not show them in the MVP UI.

## Result and selection contract

Every inventory item appears exactly once in either a matched row or fallback
row:

- matched row: original crop plus one to three returned product cards;
- fallback row: original crop with no product link;
- first product is selected by default;
- clicking another card changes only that item's selected rank.

Keep selection state in the existing result view. Extend `TryOnCreate` with a
validated `{item_id: rank}` map so the server applies the selected alternatives
before rendering. Saving sends the same locally selected snapshot. Do not add a
new endpoint or global state store.

Propagate unavailable price honestly: product `price_minor` and `currency` are
both nullable in Python and TypeScript. Preserve a known listed price in its
original currency; do not convert or invent one. Show a total only when every
selected product has a known price in the same currency; otherwise hide it.

Use returned `image_url` values directly in `<img>` and returned `product_url`
values for card links. A browser image error gets a visible placeholder; the app
does not silently replace, download, proxy or re-check the result.

## YouCam handoff

Reuse `YouCamClient.render(reference_url=...)`, which already supports remote
garment references. Keep the user photo and generated stage outputs as local
paths; pass the selected product image as `reference_url`. Do not download it
first.

Render at most one item per YouCam category. A real blouse-then-vest test made a
plausible layered image but replaced the chosen blouse details, so sequential
same-slot rendering is not a faithful combination. Keep layered items as product
rows, reject their try-on, and use single-layer outfits for the demo. Socks and
leg warmers remain recommendations rather than shoe references. Never render an
unmatched crop.

```text
if full_body selected:  user photo -> full_body -> shoes
otherwise:              user photo -> upper_body -> lower_body -> shoes
```

A full-body selection replaces upper and lower. Persist each completed stage,
use it as the next stage source, save the final image, and record only the item
IDs actually rendered. Bags, belts, jewelry, headbands and unsupported items
remain recommendations and must never be labelled as present in the preview.

## Implementation result

- `openai_discovery.py` owns raw Responses inventory and concurrent shopping.
- `openai_prompts.py` contains only the two prompts above.
- `look_builder.py` performs local normalization/crops and assembles one row per
  item.
- `try_on.py` validates selected ranks and passes remote product URLs directly
  through YouCam's existing `reference_url` input.
- The side panel uses wraparound arrows, defaults to rank one, and sends/saves
  the current combination.
- Gemini, SerpAPI, the visual verifier, Agents SDK and completion/score contracts
  were removed after the fixed gate passed.

The five fixed references completed with 30 items, 38 products, two fallbacks,
34.7 seconds mean latency and 49.1 seconds maximum latency. A real remote-URL
YouCam render succeeded in 43.3 seconds. Local tests, Ruff, TypeScript and the
extension build pass. Three clean runs in the actual demo Chrome profile remain
part of final rehearsal.

## Failure behavior

| Failure | Visible result |
| --- | --- |
| Inventory request or schema fails twice | One clear retryable analysis error. |
| One item shopper fails or finds nothing credible | That item's original crop; other items continue. |
| Price is unavailable | No price; never an estimate or zero-price label. |
| Product image fails in the browser | Explicit image placeholder; keep the link unchanged. |
| YouCam rejects a remote selected image | Fail that render clearly; add a proxy only after reproducing this failure. |

No second inventory analysis, shortlist verifier, deterministic commerce check,
cache, proxy, retailer scraper, delivery filtering, accessory VTO, social feature,
vector search, Redis, queue or worker belongs in this MVP without a measured
failure that requires it.
