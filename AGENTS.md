# WANT! Project North Star

Read this before proposing architecture or changing providers.

## Non-negotiable context

- WANT! is being built for the **YouCam API Skin AI & Apparel VTO Hackathon**.
- The submission must integrate at least one Perfect Corp. YouCam Skin or
  Fashion API. Our chosen centerpiece is **YouCam Apparel/Clothes V3**.
- YouCam must remain a real, visible, meaningful part of the end-to-end demo.
  Do not propose replacing YouCam with another renderer.
- The hackathon explicitly welcomes agentic AI workflows, but the agentic
  system should lead into YouCam VTO and demonstrate why YouCam matters.
- Official brief: https://youcam-api.devpost.com/
- Official rules: https://youcam-api.devpost.com/rules
- Submission deadline: **August 17, 2026 at 11:45 AM EDT / 9:15 PM IST**.

## Product promise

The user deliberately selects a look anywhere on the web. WANT! identifies the
visible pieces, finds the best current buyable matches, assembles one honest
Closest recreation, uses YouCam to show the user wearing the selected apparel,
and lets the user inspect links and save the look privately.

```text
capture a reference look
    -> understand the complete outfit
    -> find and verify real buyable matches
    -> choose one coherent Closest outfit
    -> render it on the user's photo with YouCam
    -> show product links and save privately
```

## Accepted runtime

```text
OpenAI visual inventory
    -> local pair/deduplication checks and item crops
    -> one concurrent OpenAI Responses shopper per distinct item
    -> hosted image + text web search, up to three products per item
    -> validate and preserve reachable product images per look
    -> retry only rows with no usable product image
    -> user-selected combination
    -> upload selected references to YouCam full-body or upper/lower, then shoes
```

The private local product catalogue and its embedding/ONNX rankers were removed
on 2026-08-16; do not reintroduce a local outfit/product database for this MVP.

### 2026-08-16 implementation result

The final raw-Responses workflow passed all five fixed references: 30 detected
items, 38 returned products, two honest fallbacks, 34.7 seconds mean latency and
49.1 seconds maximum latency. A real YouCam run accepted a returned remote image
URL directly and completed in 43.3 seconds. Gemini, SerpAPI, the visual verifier
and Agents SDK were removed after this gate passed.

On 2026-08-17, real retailer CDNs produced missing UI images and YouCam
`error_download_image` failures. Product images are now validated once and kept
as private look-scoped media; raw image-search URLs provide fallbacks and one
broader shopping retry repairs empty rows. This is not a product catalogue or
ranking store.

## MVP boundaries

- Personal use only; no social, community, publishing, sharing, or profiles.
- One evidence-backed **Closest** result. No fake Budget/Premium modes.
- Real products and direct purchase links; no second-hand inventory.
- Discovery retains at most three ranked products per detected item. The UI
  shows one item row with arrows; rank one is selected by default.
- Country delivery eligibility is deferred. Preserve known listed currencies;
  never convert or invent a missing price, and total only one shared currency.
- If there is no credible match, keep the original visible item as an unlinked
  preview reference instead of hallucinating a product.
- Search and save meaningful accessories, but never claim an accessory appears
  in the YouCam output unless that render was actually performed and verified.
- SQLite/local persistence is sufficient. No Redis, Celery, vector database, or
  distributed services for the hackathon MVP.
- API keys stay server-side and out of extension bundles, logs, fixtures, and
  committed files.

## Decision discipline

- Read `AGENTS.md`, `docs/product-spec.md`, and `docs/implementation-plan.md`
  before revising the architecture.
- Read current official provider documentation; do not rely on stale model or
  API knowledge.
- Measure any future provider change on the same fixed references before
  replacing the accepted runtime.
- Optimize for a reliable, polished 1-3 minute judged demo and clear consumer
  value, not platform breadth.
