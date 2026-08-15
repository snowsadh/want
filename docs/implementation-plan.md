# WANT! — Implementation Plan

> Status: Approved direction, ready for implementation  
> Created: 2026-08-15  
> Scope: Hackathon MVP described in `docs/product-spec.md`

## 1. Delivery Goal

Build one reliable personal-use loop:

```text
upload the user's photo
    -> activate the extension on any page
    -> select a look with a rectangle
    -> analyze the selected region
    -> retrieve real products
    -> assemble Closest, Budget, and Premium outfits
    -> render the selected apparel outfit on the user
    -> inspect product links
    -> save and reopen the look privately
```

The MVP does not include Explore, community profiles, public looks,
publishing, sharing, follows, feeds, or social authentication.

### Scope guardrails

Work enters the MVP only if it directly completes the loop above, satisfies a
hackathon requirement, or removes a demonstrated reliability risk. In
particular:

- Build a product, not a general platform.
- Prefer one real integration over several partial providers.
- Keep extension and backend code in one repository and deploy the backend as
  one process.
- Do not add infrastructure because it may be useful later.
- Stop retrieval experimentation as soon as one approach is visibly reliable
  for the demo catalog.
- After the core loop is stable, spend remaining time on reliability and
  presentation rather than stretch features.

## 2. Technical Baseline

- Chrome Manifest V3 extension using React and TypeScript.
- Vite-based extension build with separate side-panel, content-script, and
  service-worker entry points.
- FastAPI backend using Pydantic request and response models.
- Backend Pydantic/OpenAPI models as the canonical API contract. Keep the small
  set of TypeScript API types beside the extension client initially; automate
  generation only if manual drift becomes a real problem.
- SQLite for profile metadata and saved looks.
- Local filesystem storage for uploaded and generated images in development,
  kept in one small storage module so a deployment change does not touch API
  routes or domain logic.
- Handle YouCam's task lifecycle inside the FastAPI process; do not add Redis,
  Celery, or a separate worker for the hackathon build.
- Use narrow boundaries only around external services and retrieval logic that
  we already know may change.

## 3. Repository Shape

```text
ucam/
|- apps/
|  |- extension/             # MV3 service worker, capture overlay, side panel
|  `- api/                   # FastAPI application and domain services
|- data/
|  `- catalog/               # Authorized normalized product catalog
|- tests/
|  `- fixtures/              # Capture, analysis, catalog, and VTO test inputs
`- docs/
```

The backend remains a modular monolith. Separate deployable services would add
coordination cost without improving the hackathon demonstration.

## 4. Stable Boundaries

Use four narrow boundaries before selecting the final search or vector
approach:

```text
LookAnalyzer
    analyze(captured_image) -> LookAnalysis

ProductCatalog
    find_candidates(component, region, currency) -> Product[]

RetrievalEngine
    rank(look, candidates, constraints) -> RankedProduct[]

TryOnClient
    render(source_image, garment_image, category) -> TryOnResult
```

Initial implementations:

- One real structured vision-model client.
- A curated normalized catalog provider.
- A deterministic weighted retrieval baseline.
- One real YouCam client.
- Straightforward outfit-building functions, SQLite queries, and local media
  storage; these do not need abstract interfaces in the MVP.

Tests and early UI development may use saved, schema-valid fixture responses.
Those fixtures are test inputs, never a runtime/demo substitute for real look
analysis, real products, or a real YouCam result.

## 5. Core Contracts

Define these Pydantic models first and expose them through OpenAPI:

- `UserProfile`: region, currency, optional spending range, private photo ref.
- `LookAnalysis`: garment, shoe, accessory, palette, proportion, and layering
  data from the product specification.
- `Product`: normalized identity, slot, attributes, price, availability, image,
  URL, provider, freshness, and VTO compatibility.
- `RankedProduct`: product plus component scores and an explainable total score.
- `OutfitVariant`: mode, selected products, total price, relative match score,
  and which items can appear in the personalized render.
- `TryOnJob`: status, stage, inputs, error, latency, unit use, and result ref.
- `SavedLook`: source URL, private capture ref, all three variants, selected
  mode, personalized result ref, and a snapshot of product price/link data.

Product snapshots belong in a saved look so reopening it does not silently
change the original result when the catalog changes.

## 6. Minimal API Surface

```text
GET    /api/health
GET    /api/profile
PUT    /api/profile             # metadata plus personal photo

POST   /api/looks               # analyze capture and build three outfits

POST   /api/try-ons
GET    /api/try-ons/{job_id}

POST   /api/saved-looks
GET    /api/saved-looks
GET    /api/saved-looks/{saved_look_id}
DELETE /api/saved-looks/{saved_look_id}
```

The extension communicates only with this API. Provider-specific identifiers,
temporary YouCam URLs, and API credentials never enter extension storage.

## 7. Extension Responsibilities

### Service worker

- Open the side panel from the toolbar action and optional keyboard shortcut.
- Initiate `captureVisibleTab` only after explicit user activation.
- Coordinate capture data between the active tab and side panel.

### Content script

- Mount the rectangular selection overlay only after activation.
- Return the rectangle, viewport dimensions, scroll position, and device pixel
  ratio needed to crop the screenshot accurately.
- Remove the overlay completely on confirm, cancel, or navigation.

### Side panel

- Onboarding and real user-photo upload.
- Capture, analysis, retrieval, and try-on progress states.
- Closest, Budget, and Premium switching.
- Honest separation of rendered items and recommendation-only items.
- Product links, totals, match indicators, save, and private saved-look list.

## 8. Build Phases

### Phase 1 — Scaffold and contracts

- Create the repository structure and local development commands.
- Scaffold the MV3 extension and FastAPI application.
- Add one health endpoint and minimal configuration loading.
- Define only the Pydantic and TypeScript types used by the first vertical
  slice.
- Use saved fixture responses to exercise the side-panel states before live
  integrations are connected.

Exit condition: the side panel loads, calls the backend health endpoint, and
can display a contract-valid fixture result.

Timebox: keep this scaffold deliberately small and move to the risk spikes as
soon as the exit condition passes.

### Phase 2 — Highest-risk spikes

- Make and record one real YouCam upper-body call.
- Make and record one real YouCam lower-body call.
- Run both sequentially in both orders and inspect preservation and drift.
- Measure latency, unit use, temporary URL lifetime, failures, and retry needs.
- Validate capture and crop coordinates on an ordinary image and paused video
  on the primary demo setup. Test zoom/high-DPI behavior only if the demo setup
  uses it; canvas is not a pre-demo gate.
- Run the identification, live candidate-source, and ranking tests defined in
  `docs/identification-retrieval-decision.md` on the same fixed captures.
- Select the simplest item-identification and retrieval path that passes those
  gates before building the main vertical slice.

Exit condition: at least one repeatable two-piece render and pixel-accurate
captures on the primary demo machine, plus a measured path from capture to
credible purchasable products.

### Phase 3 — Thin end-to-end vertical slice

- Implement real onboarding and private photo persistence.
- Connect rectangular capture to the backend.
- Produce structured look analysis.
- Load a small, authorized catalog of real linked products.
- Use the deterministic retrieval baseline to construct all three modes.
- Generate Closest first and allow on-demand rendering of other modes.
- Save and reopen the complete result from SQLite.

Exit condition: the full core loop works without manually editing state or
substituting a hardcoded user.

### Phase 4 — Reliability and presentation

- Add errors, timeouts, caching, and at most one safe retry where the measured
  failure behavior justifies it.
- Verify secrets and temporary provider URLs remain server-side.
- Add loading, empty, offline, and partial-result states.
- Confirm every displayed product has a valid image, price, and purchase URL.
- Test extension installation and the complete demo from a clean profile.
- Capture screenshots and record the final 1–3 minute demo.

Exit condition: three consecutive clean end-to-end demo runs on the intended
machine and deployment.

## 9. Retrieval Experiment Rules

The initial baseline should score normalized fields directly, for example:

```text
hard filter: body slot and category compatibility
weighted score: visual + color + material + silhouette + details
mode adjustment: price ceiling/penalty or premium-quality metadata
outfit rerank: palette, layering, proportions, and total-price coherence
```

Experiments may change candidate generation or ranking, but must return the
same `RankedProduct` contract. Do not introduce a vector database until the
evaluation size or measured query latency justifies it; an in-process index is
acceptable for the small bake-off.

## 10. MVP Test Gate

The build is demo-ready only when all of these pass:

- Nothing is captured before explicit activation.
- Cancel uploads nothing and removes the overlay.
- The selected rectangle is the image analyzed.
- The user uploads a real personal photo through onboarding.
- At least upper and lower apparel are matched to real purchasable products.
- A real sequential YouCam result is produced and persisted.
- Closest, Budget, and Premium contain coherent product combinations.
- Unsupported accessories are labeled as recommendations, not rendered items.
- Every product link is individually accessible.
- A look can be saved, listed, reopened, and deleted privately.
- No social or public-sharing UI is present.
- API keys are absent from the extension bundle and browser storage.

## 11. Deferred Work

- Live multi-retailer aggregation beyond one reliable provider/catalog.
- A dedicated vector service or distributed search infrastructure.
- All accessory VTO integrations.
- Public profiles, community looks, Explore, publishing, sharing, and feeds.
- Multi-user account infrastructure unless required for deployment security.
- Checkout, sizing/fit claims, and mature price/availability monitoring.
