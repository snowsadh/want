# WANT! — Clothing Identification and Retrieval Decision Brief

> Status: Options narrowed; empirical decision required  
> Created: 2026-08-15  
> Purpose: Choose a reliable path from a captured outfit to real purchasable
> products without committing the product to fragile search infrastructure.

## 1. The Decision Is Three Decisions

```text
captured person
    -> A. identify and crop each visible clothing item
    -> B. obtain plausible purchasable candidates for each item
    -> C. rank those candidates and assemble coherent outfits
```

These layers must stay separate. A strong ranker cannot recover a suitable
product that the candidate source never returned, and a broad product search
cannot compensate for an incorrect garment crop or category.

## 2. Provisional Recommendation

Test this path first:

1. Use one multimodal vision call to produce structured garment data, normalized
   bounding boxes, and outfit-level relationships.
2. Crop each item with a small amount of surrounding context. Do not require
   pixel masks unless bounding-box retrieval demonstrably fails.
3. Test live product discovery through a supported shopping/visual-search API.
4. Normalize and hard-filter candidates by category, region, price presence,
   availability, image, and purchase URL.
5. Rerank the survivors with a fashion-specific image/text embedding plus the
   structured attributes from step 1.
6. Keep a small catalog of real products as the reliable demo path if live
   discovery fails the test gate.

This is a recommendation for a small test, not permission to build every layer.
If a simpler path passes the gate, stop there.

## 3. Item Identification Options

### Option A — Multimodal model with structured output

One image request returns:

- body slot and normalized garment category;
- bounding box for each item;
- color, pattern, material appearance, silhouette, and details;
- visible/occluded/uncertain status;
- outfit palette, layering, and proportions.

Why it is the first candidate:

- One integration and one inference call.
- Handles open-ended fashion language better than a fixed detector taxonomy.
- Can describe relationships such as tucked, layered, oversized, or cropped.
- Structured output can be validated directly with Pydantic.

Main risks:

- Bounding boxes and fine material claims may be inconsistent.
- The model may confidently infer details that are not visible.
- Output and latency can change with model versions.

Mitigation:

- Require `unknown` for non-visible attributes.
- Validate categories against our small enum.
- Reject invalid or tiny boxes.
- Save model and prompt versions with evaluation results.
- Use deterministic settings where the provider supports them.

Gemini is the strongest first API candidate because its current official image
documentation explicitly supports object detection, segmentation, normalized
boxes, and schema-constrained JSON. That does not mean it wins without testing
on our fashion captures.

Reference: [Gemini image understanding](https://ai.google.dev/gemini-api/docs/image-understanding)
and [structured output](https://ai.google.dev/gemini-api/docs/structured-output).

### Option B — Grounding DINO or Florence-2, optionally followed by SAM 2

Run a local/open model to detect prompted clothing categories; optionally use
SAM 2 to create item masks. A multimodal model or classifier is still needed
for rich fashion attributes and outfit relationships.

Advantages:

- Greater control over boxes, masks, thresholds, and model versions.
- No per-image detection API dependency after deployment.
- Captures can remain on our infrastructure.

Costs and failure modes:

- Adds PyTorch, model weights, GPU/CPU performance work, image preprocessing,
  threshold tuning, and deployment complexity.
- Open-vocabulary detection identifies objects but does not by itself provide
  reliable material, silhouette, construction, or outfit relationships.
- SAM 2 requires prompts from another detector and introduces another model;
  its official setup recommends a recent PyTorch stack and may compile CUDA
  components.

This is a fallback only if the multimodal API fails garment localization. It is
not justified merely because segmentation appears technically sophisticated.

References: [Grounding DINO](https://github.com/IDEA-Research/GroundingDINO),
[Florence-2](https://huggingface.co/microsoft/Florence-2-base), and
[SAM 2](https://github.com/facebookresearch/sam2).

### Option C — Fashion-specific detector/retrieval network

DeepFashion2 and related work directly address detection, segmentation, and
consumer-to-shop retrieval. They are useful benchmarks and future training
sources, but are not the best first implementation.

Why not now:

- A benchmark and research baseline are not a maintained product API.
- Training or adapting a model adds dataset, GPU, serving, and evaluation work.
- Fixed research categories may not match our desired product taxonomy.
- It still does not solve live purchasable inventory.

Reference: [DeepFashion2 paper](https://openaccess.thecvf.com/content_CVPR_2019/papers/Ge_DeepFashion2_A_Versatile_Benchmark_for_Detection_Pose_Estimation_Segmentation_and_CVPR_2019_paper.pdf).

## 4. Candidate Inventory Options

### Option 1 — Small controlled catalog of real products

Create a normalized catalog from a source whose terms permit our use. Store
real product IDs, images, current price/currency, availability, purchase URLs,
attributes, and timestamps.

Strengths:

- Fast, deterministic, cacheable, and easy to inspect.
- We can guarantee every displayed result is actually a product.
- Ideal for proving ranking, outfit assembly, and VTO compatibility.

Weaknesses:

- Limited fashion coverage.
- Requires a legitimate source and refresh process.
- Users may capture a look not represented in the catalog.

Important: curated does not mean hardcoded query-to-answer mappings. The search
must genuinely rank the catalog for arbitrary captures. Product selection can
be intentionally broad enough for the demo while remaining real.

### Option 2 — Third-party Google Lens/Shopping API

A provider such as SerpApi can accept an uploaded item crop, return Lens
product/visual matches, localize by country, and provide product fields when
Google exposes them. Text can also be supplied to constrain a product search.

Strengths:

- Broad, current web inventory without building retailer scrapers.
- Image and text signals can both seed candidate generation.
- Product results may include source, link, image, price, currency, and stock.

Risks:

- It is a paid scraping/search intermediary rather than a retailer-owned
  product feed.
- Result completeness and fields vary by query and country.
- Its own 2025–2026 release notes record empty results, inconsistent result
  counts, 500 errors, latency, and missing price/stock fixes.
- Uploaded image privacy and retention must be reviewed; the documented
  zero-trace mode is enterprise-only.
- Visual matches can include articles and social pages rather than buyable
  products, so normalization and filtering remain mandatory.

This is worth a small live test, but not safe enough to assume as the only demo
source before measuring it.

References: [SerpApi Google Lens API](https://serpapi.com/google-lens-api) and
[release notes](https://serpapi.com/google-lens-api/release-notes).

### Option 3 — Official marketplace API such as eBay Browse

eBay's Browse API supports keyword and image search and returns purchasable
listing data. On paper it is a strong single-provider source.

Why it is not the default hackathon path:

- Production access requires an application, approval, and agreements; eBay
  explicitly says approval is not guaranteed.
- Image search is supported only for the US, Germany, UK, and Australia.
- It cannot satisfy an India-localized product experience.
- Sandbox results do not prove that the judged deployment can use production
  inventory.

Use it only if production access already exists for a supported demo region.

References: [eBay Browse API](https://developer.ebay.com/develop/api/buy),
[production requirements](https://developer.ebay.com/api-docs/buy/buy-requirements.html),
and [marketplace support](https://developer.ebay.com/api-docs/buy/ref-marketplace-supported.html).

### Option 4 — Managed product-search service

Google Vision Product Search can search an uploaded apparel product set by
image and labels, but it does not supply inventory; we must populate the entire
catalog ourselves. The service is also currently in maintenance mode, with
Google directing scalability-focused users toward Vision Warehouse.

For our small catalog, local embeddings and a matrix similarity search are
simpler, cheaper, and easier to debug.

Reference: [Google Vision Product Search](https://cloud.google.com/vision/product-search/docs/searching).

### Rejected — custom retailer scraping

Do not build scrapers for retailer pages. They create terms, breakage, bot
protection, parsing, price freshness, and maintenance problems before we have
proved the product.

## 5. Ranking Options

### Baseline — structured scoring

Hard-filter category/body-slot incompatibility, then score normalized product
attributes against the identified garment:

```text
category + color + pattern + material + silhouette + distinctive details
```

This is quick to debug and provides understandable reasons, but text metadata
is often incomplete and it may miss a visually similar product described with
different words.

### Candidate — fashion-specific multimodal embedding

Embed the garment crop and product images into the same space, then rank with
cosine similarity. Add text embeddings for the structured description when
useful. For a small catalog or candidate list, normalized NumPy matrix
multiplication is sufficient; no vector database is needed.

`Marqo-FashionSigLIP` is the first model worth testing. Its maintainers publish
fashion-specific evaluation code and report stronger average retrieval and
category metrics than general OpenCLIP/SigLIP and older FashionCLIP variants.
Those published aggregate benchmarks are evidence to test it, not proof that
it will win on our captured-person-to-product problem.

Pin the selected model revision and inspect any custom model-loading code; do
not execute an unpinned remote `trust_remote_code` implementation in the app.

Reference: [Marqo-FashionCLIP/FashionSigLIP repository](https://github.com/marqo-ai/marqo-FashionCLIP)
and the original [FashionCLIP paper](https://arxiv.org/abs/2204.03972).

### Recommended ranking — constrained hybrid

```text
1. hard reject wrong body slot/category and non-buyable candidates
2. fashion image similarity
3. structured attribute agreement
4. mode-specific price/quality adjustment
5. outfit-level palette, proportion, and layering check
```

Do not let a single cosine score overrule an obviously wrong category. Do not
present the internal weighted score as scientific confidence.

### Deferred — multimodal-model reranking

A vision model could compare the reference item with a collage of product
candidates. It may reason well about silhouette and details but adds another
paid inference, nondeterminism, prompt/version sensitivity, and image-layout
work. Test it only if the hybrid ranker fails in a repeatable way.

## 6. Small Decision Experiment

Use 8–12 representative captures containing:

- solid and patterned garments;
- fitted and oversized silhouettes;
- layered upper-body clothing;
- partially occluded clothing;
- a paused video frame;
- at least one shoe and one accessory;
- light and dark scenes.

### Test A — identification

Run the multimodal structured-output approach and record for every visible
item:

- correct body slot/category;
- usable bounding box;
- major color/pattern accuracy;
- silhouette/material/detail usefulness;
- false or missing items;
- latency and cost.

Pass gate: upper and lower garments are correctly identified with usable boxes
on at least 10 of 12 captures, with no invented primary garment. Treat this as
a provisional threshold and inspect every failure.

Only if this fails because of localization should we test Florence-2 or
Grounding DINO. Do not test SAM 2 unless masks are shown to improve retrieval.

### Test B — live candidate source

For each accepted garment crop, request product results from the proposed live
provider and record:

- number of genuinely buyable results;
- correct-category candidates in the first 10;
- valid product image, price, currency, availability, and direct URL;
- region relevance;
- latency, errors, and repeated-query consistency.

Pass gate: at least one credible purchasable candidate for 90% of the primary
garments, no broken demo-critical links, and latency acceptable when item
searches run in parallel. Any privacy/terms review must also pass.

### Test C — ranking

For the same fixed candidates, compare only:

1. structured scoring baseline;
2. category-filtered FashionSigLIP plus structured scoring.

Blindly inspect the top three for each garment using a short rubric:

- same garment type;
- visually recognizable color/pattern;
- similar silhouette and construction;
- plausible recreation of the reference;
- stable latency.

Adopt FashionSigLIP only if it creates a clear visible improvement. Otherwise
ship the structured baseline.

## 7. Smoothness Rules

- Analyze the full selected look once, not once per item.
- Search separate garment items concurrently after analysis.
- Crop and transmit garment regions, not the captured person's face, to a
  third-party visual-search provider where technically possible.
- Cache analysis by capture hash and product search by garment-crop/query hash.
- Apply hard timeouts and return partial results honestly.
- Never show a result without a product image and direct purchase URL.
- Prefer a cached, real catalog result over waiting indefinitely for a live
  provider.
- Log the input hash, model/provider version, timings, candidate counts, and
  rejection reasons so failures can be reproduced.

## 8. Current Decision

Do not choose a vector database, detector stack, or marketplace integration
yet. The first concrete test should be:

```text
multimodal structured identification with boxes
    + live Lens/Shopping candidate-source trial
    + FashionSigLIP hybrid ranking against the same fixed candidates
```

The likely MVP outcome is a multimodal identifier plus a controlled real
catalog and local hybrid ranking, with live search used only if its measured
reliability and data terms are acceptable. This preserves product quality
without making the demo depend on an unstable web-search result.
