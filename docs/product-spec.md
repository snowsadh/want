# WANT! — Product Specification

> Personal-use hackathon MVP. Last updated 2026-08-17.

## Promise

The user selects an outfit anywhere on the web. WANT! identifies every distinct
visible wearable, finds current buyable matches, lets the user choose one match
per item, renders supported apparel through YouCam, and saves the result
privately.

There is one result mode: **Closest**. There are no Budget, Premium, social,
sharing or public-profile modes.

## User flow

1. Upload a YouCam-compatible full-body photo.
2. Draw around one look on a normal webpage and confirm the capture.
3. OpenAI inventories the visible items and searches for each item concurrently.
4. Each item row shows zero to three products; rank one is selected by default.
5. Use the row arrows to change any selection.
6. Press **Try this look** to render that exact selected combination with YouCam.
7. Inspect direct product links or save the selected snapshot locally.

Normal images and paused video frames are supported. Firefox-owned pages such as
`about:` pages and Firefox Add-ons are outside extension access.

## Outfit inventory

Analyze only the selected pixels. Return exactly one record per distinct visible
garment, footwear/legwear item or meaningful accessory, including hats,
headbands, substantial hair accessories and clearly visible statement jewelry.

Each record contains category, body slot, tight normalized box, visibility,
colors, silhouette, material appearance, pattern/graphic and visible details.
Do not invent hidden items, duplicate left/right pairs, turn a tied garment into
a belt, or merge separately shoppable layers.

## Product discovery

```text
OpenAI inventory
    -> local schema, pair and duplicate checks + crops
    -> one concurrent OpenAI Responses shopper per item
    -> hosted image + text web search
    -> one broader retry only for rows with no usable product image
    -> 0–3 ordered products or original-crop fallback
```

Search for the identical product first. Otherwise rank by:

```text
color + style/silhouette > design/pattern > print/graphic > material/details
```

Every returned option must be a distinct new-retail product with a direct
product-page URL and matching image URL. Preserve any listed price and its
original currency; never convert or invent one. Delivery country filtering is
deferred.

When equally useful images exist, prefer a model-worn image only when the target
item is clearly isolated; otherwise use the clean product image so YouCam is not
confused by other clothing.

The application does not reopen product pages or run a second semantic verifier.
It downloads each returned product image once, keeps only images that are
publicly reachable and decodable, and stores a private look-scoped JPEG for the
UI and YouCam handoff. Canonical and thumbnail URLs from the raw image-search
results are tried before a product is discarded. An empty row receives one
broader same-category shopping retry. A row is never padded with an imageless
or wrong-category product.

## YouCam rendering

YouCam Clothes V3 is the hackathon centerpiece. The selected validated product
image is uploaded through the Clothes V3 File API as the reference:

```text
full_body -> shoes
OR
upper_body -> lower_body -> shoes
```

A full-body item replaces upper and lower. Clothes V3 accepts one reference per
garment region, and a measured blouse-then-vest pass replaced the blouse details
instead of preserving both independently selected products. The demo therefore
uses one best visible layer per region; other layered items remain shopping
recommendations rather than being presented as a faithful combination. Socks, stockings, tights,
hosiery, obvious underlayers, leg warmers, tied waist layers and unsupported
accessories remain shopping-only recommendations. Record and label only item IDs
actually rendered.

Each completed YouCam stage is persisted locally and becomes the next stage
source. The final persisted image—not a temporary provider URL—is shown and
saved. If a retailer blocks YouCam from downloading one selected reference,
preserve any successful stages, keep that product shoppable but label it not in
the preview, and fail the try-on only when no selected garment can be rendered.

## Results and saved looks

The result view contains the current YouCam image or original capture, one row
per detected item, arrow-selectable products, direct links, known prices and
unlinked crop fallbacks. Changing a selection invalidates an older preview.

A saved look snapshots the capture, final render, selected ranks, products,
prices, links and source URL so reopening it does not silently change.

## Privacy and scope

- One local profile; SQLite stores profile metadata and saved snapshots.
- Local files store private photos, captures and generated images.
- API keys stay server-side and out of the extension, logs, fixtures and Git.
- No product catalogue, vector index, Redis, worker, auth, social layer,
  checkout or separate service. Product images are retained only within their
  private look snapshot.
- Generated imagery is a visual preview, not a claim about physical fit.

## Demo acceptance

The MVP is ready when the actual Firefox profile completes three consecutive
capture-to-saved-YouCam runs inside 1–3 minutes without a fabricated inventory
item, unsupported render claim or broken visible interaction.

Official references:

- https://youcam-api.devpost.com/
- https://youcam-api.devpost.com/rules
- https://docs.perfectcorp.com/reference/ai_clothes/section/overview
- https://docs.perfectcorp.com/develop/introduction

Submission deadline: **August 17, 2026 at 11:45 AM EDT / 9:15 PM IST**.
