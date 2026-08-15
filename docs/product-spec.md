# WANT! — Living Product Specification

> Status: Draft source of truth  
> Last updated: 2026-08-15  
> Purpose: Record confirmed product decisions, distinguish them from assumptions, and guide implementation and hackathon submission work.

## 1. Product Thesis

WANT! is a user-triggered Chrome extension that turns a look discovered anywhere on the web into purchasable outfit options and shows the user wearing the selected option before they buy it.

The concise promise is:

> Point at any look online. WANT! finds real pieces that recreate it, then shows you wearing the best combination before you buy.

The inspiration image is a **visual search query**. WANT! does not directly transfer the captured person's clothing onto the user.

## 2. Problem

Fashion desire often begins outside a store: in a video, article, photograph, blog, social post, or other visual content. Converting that inspiration into something buyable currently requires the user to:

1. Identify each visible item.
2. Translate visual details into search terms.
3. Search across stores.
4. Find available alternatives at an acceptable price.
5. Decide whether the selected items recreate the complete look.
6. Imagine how the outfit will look on them.

WANT! compresses that journey into a deliberate capture and a personalized, shoppable result.

## 3. Core Experience

```text
See a desirable look anywhere online
    -> activate WANT!
    -> draw a rectangle around the person
    -> analyze only the selected region
    -> identify garments, shoes, and accessories
    -> find real purchasable matches
    -> assemble Closest, Budget, and Premium options
    -> generate the user wearing a selected apparel option
    -> inspect and open every linked product
    -> save the look
```

### 3.1 Explicit capture interaction

WANT! performs no visual analysis during ordinary browsing.

The user must deliberately:

1. Click the extension action or use a keyboard shortcut.
2. Enter a screenshot-like selection mode.
3. Draw a rectangle around the desired person/look.
4. Confirm or cancel the selection.

Only the confirmed rectangular region is sent for processing.

This interaction should work over ordinary images, video frames, canvas content, and pages containing multiple people.

### 3.2 Capture non-goals

WANT! will not:

- Continuously monitor the page or screen.
- Detect potential models before activation.
- Inject buttons over images during normal browsing.
- Use a right-click context-menu flow.
- Analyze content without an explicit user action.

## 4. First-Time Setup

The user completes real onboarding and supplies their own image. The prototype must not ship with or silently substitute a hardcoded demo user.

Minimum setup:

- Upload a YouCam-compatible full-body photo.
- Confirm region and currency.
- Optionally set a typical spending range.

Additional face, ear, hand, or wrist photos should be requested only when the user invokes a feature that genuinely requires them. They should not burden initial onboarding.

For a hackathon demonstration, the presenter may use a previously prepared valid personal photo, but must upload it through the real product flow.

## 5. Look Understanding

The selected region is converted into structured look data. The output should represent both individual components and the relationships that make the complete look recognizable.

Candidate structure:

```json
{
  "garments": [
    {
      "slot": "upper_body",
      "category": "cardigan",
      "color": "cream",
      "material": "ribbed knit",
      "silhouette": "relaxed",
      "details": ["v-neck", "front buttons"]
    }
  ],
  "shoes": [],
  "accessories": [],
  "palette": [],
  "overall_style": "",
  "proportions": "",
  "layering": ""
}
```

The system must not reduce the look to loose keywords. It should retain:

- Garment category and body slot.
- Color and palette relationships.
- Material and visible texture.
- Silhouette and proportion.
- Layering.
- Distinctive construction details.
- Overall aesthetic.
- Visible shoes and accessories.

## 6. Product Retrieval

The captured person's outfit is used to search **real, purchasable inventory**.

Each product record should eventually support:

```text
id
name
retailer/brand
category and body slot
description and structured attributes
price and currency
availability
product image
purchase URL
visual embedding
VTO compatibility metadata
source and last-updated timestamp
```

Retrieval should combine visual similarity with structured constraints rather than relying only on generated search terms.

Candidate signals include:

- Visual embedding similarity.
- Correct garment/accessory category.
- Color and material similarity.
- Silhouette and construction similarity.
- Outfit-level palette and proportion compatibility.
- Availability.
- Region and delivery eligibility.
- Price-mode constraints.
- VTO input compatibility.

### 6.1 Catalog architecture

The intended architecture supports multiple inventory providers behind one normalized interface:

```text
ProductProvider
    |- CuratedCatalogProvider
    |- MarketplaceProvider
    |- ShoppingSearchProvider
    `- FutureRetailerProvider
```

The hackathon implementation should prioritize a reliable, normalized catalog and may add a live provider if it improves the real demo without introducing fragility.

Building custom retailer scrapers is not yet approved. Any third-party data source must be authorized and compatible with the hackathon rules and the source's terms.

## 7. Outfit Construction Modes

WANT! returns three coherent alternatives, not three independent piles of products.

### 7.1 Closest

Prioritizes faithful recreation of the captured look:

- Visual similarity.
- Silhouette and proportions.
- Palette.
- Materials and details.
- Overall outfit coherence.

### 7.2 Budget

Preserves the recognizable look while minimizing total price or respecting a user-defined ceiling.

Budget is not simply the cheapest item in every category; the final combination must remain coherent.

### 7.3 Premium

Prioritizes a higher-quality or elevated interpretation while retaining the reference aesthetic.

"Premium" still needs an operational definition. Price alone is not sufficient; potential signals include retailer tier, materials, construction, brand positioning, and product quality metadata.

## 8. Personalized Rendering

### 8.1 Apparel

YouCam AI Clothes V3 applies one clothing reference and one garment category per task. WANT! therefore constructs a multi-piece apparel result sequentially.

Conceptual flow:

```text
User full-body photo
    -> apply selected upper-body product
    -> download and persist result
    -> use result as the next source
    -> apply selected lower-body product
    -> persist final apparel result
```

Implementation rules discovered from the official documentation and comparable hackathon implementations:

- Set `garment_category` explicitly; do not rely on `auto`.
- Preserve the unaffected body region between stages.
- Download generated result bytes promptly instead of persisting temporary result URLs.
- Cache each render by user image, product image, category, and relevant options.
- Reuse uploaded file identifiers where supported.
- Treat rendering errors as recoverable per-item failures.

The optimal upper/lower order must be tested empirically using patterned and layered garments.

### 8.2 Multiple modes

All three outfit combinations can be retrieved immediately, but generating all three personalized renders synchronously may create unnecessary latency and cost.

Working product strategy:

1. Retrieve Closest, Budget, and Premium combinations.
2. Generate Closest first.
3. Present Budget and Premium product combinations immediately.
4. Generate another personalized result when the user chooses **Try this version**.
5. Cache completed renders so saved and repeated looks do not consume units again.

This strategy remains subject to latency testing.

## 9. Shoes and Accessories

Accessories are first-class parts of look analysis and product retrieval.

Every detected accessory may be:

- Matched to buyable products.
- Included in price totals where appropriate.
- Opened through a product link.
- Saved as part of the look.

Visualization support has three honest levels:

### 9.1 Included in the apparel result

Items reliably carried through the final sequential apparel render.

### 9.2 Dedicated try-on available

YouCam currently exposes specialized workflows for categories including shoes, earrings, necklaces, rings, bracelets, and watches. These may require a separate face, hand, wrist, or category-specific user image.

Dedicated accessory results should normally be non-destructive previews rather than replacements for the canonical apparel result.

### 9.3 Shoppable recommendation only

Unsupported or unreliable categories, such as bags or belts, remain linked recommendations. The UI must not imply they appear in the generated image when they do not.

Recommended interface vocabulary:

```text
Wearing in this preview
Try-on available
Complete the look
```

The hackathon MVP proves the apparel flow. Dedicated accessory try-on is
deferred; detected accessories remain honest, linked recommendations.

## 10. Results Experience

The side panel should prioritize the emotional payoff: the user seeing themselves in a purchasable recreation.

Information hierarchy:

1. Personalized result image.
2. Closest / Budget / Premium mode switcher.
3. Total price and understandable match indicator.
4. Products represented in the preview.
5. Try-on-capable accessories.
6. Remaining "complete the look" products.
7. Save action.

Each product should be individually inspectable and link to its source listing.

Match values must be presented as consumer-friendly relative scores, not scientific certainty.

## 11. Saved Looks

Saving is part of the MVP.

A saved look may retain:

- Personalized render.
- Selected mode.
- Closest, Budget, and Premium combinations.
- Product identifiers, prices, and links.
- Total price and match score.
- Source-page URL.
- Private captured region.
- Availability timestamps.

Saved looks are private and intended for the current user's personal use. The
hackathon build does not include Explore, community profiles, publishing,
sharing, follows, feeds, or other social features.

## 12. Privacy and Trust

WANT! should make its user-triggered behavior legible:

- Nothing is captured or analyzed before activation.
- The selection overlay clearly shows the exact region being captured.
- Cancel exits without uploading anything.
- User profile images are not public.
- Original captures are private.
- API keys remain server-side.
- The UI distinguishes rendered items from suggested-only items.
- Product availability and prices carry timestamps where practical.

Storage location, retention, and deletion remain to be designed. Multi-user
account behavior is deferred beyond the personal-use MVP.

## 13. Visual Direction

### 13.1 Confirmed target

The interface should feel **sleek, precise, Apple/macOS-like, classy, and luxurious**.

This refers to product qualities rather than copying Apple assets:

- Quiet confidence instead of visual noise.
- Strong hierarchy with generous negative space.
- Precise alignment and restrained typography.
- Material depth used purposefully.
- Subtle, responsive motion.
- Controls that feel tactile but not ornamental.
- Premium image presentation.

### 13.2 Working interpretation

The likely direction is a cool, near-black or graphite side panel with controlled translucency, fine neutral borders, soft elevation, and one restrained brand accent. The captured selection and personalized render should supply most of the color.

Avoid:

- Generic gradient-heavy AI styling.
- Excessive glassmorphism.
- Neon cyberpunk effects.
- Dense dashboard layouts.
- Decorative charts or fake precision.
- Overuse of pills, badges, and glowing borders.
- Literal copying of macOS windows or Apple trademarks.

### 13.3 Product-specific signature

The memorable moment should be the transition from the user's selected rectangle into the personalized result—not decorative background effects.

One candidate motion concept:

```text
selection locks
    -> selected region gently compresses toward the side panel
    -> analysis stages resolve into product pieces
    -> final personalized image reveals cleanly
```

This is a direction for later prototyping, not yet a final animation specification.

### 13.4 Open visual decisions

- Light, dark, or adaptive default.
- Brand accent and final color tokens.
- Typography strategy across macOS and Windows.
- Panel width and responsive behavior.
- Amount of translucency allowed in Chrome's side panel.
- Motion timing and reduced-motion behavior.
- Final icon and wordmark treatment.

## 14. Hackathon Requirements

The working prototype must:

- Integrate at least one YouCam Skin or Fashion API.
- Demonstrate clear consumer or retail value.
- Install and run consistently on its intended platform.
- Behave as shown in its video and description.
- Provide a complete repository, assets, and setup/testing instructions.
- Include screenshots.
- Include a public 1–3 minute end-to-end demo video explaining the YouCam integration.
- Remain available to judges during the judging period.
- Use third-party APIs, data, media, and software only with appropriate authorization.

Deadline: **August 17, 2026 at 11:45 AM EDT / 9:15 PM IST**.

Official references:

- https://youcam-api.devpost.com/
- https://youcam-api.devpost.com/rules
- https://docs.perfectcorp.com/reference/ai_clothes/section/overview
- https://docs.perfectcorp.com/develop/introduction

Judging is equally weighted across:

- Technological Implementation.
- Design.
- Potential Impact.
- Quality of the Idea.

## 15. MVP Boundaries

### Confirmed MVP capabilities

- Chrome extension.
- Explicit rectangular capture mode.
- Real user onboarding and photo upload.
- Structured look analysis.
- Retrieval of real purchasable products.
- Closest, Budget, and Premium outfit construction.
- At least one genuine sequential apparel VTO flow.
- Individually linked product elements.
- Save and reopen a look.
- Polished side-panel experience.
- Real end-to-end demonstration.

### Deferred candidates — not part of the current implementation plan

- Live inventory provider in addition to the normalized demo catalog.
- One dedicated accessory try-on.
- Price/availability refresh.

### Explicit non-goals for the first build

- Passive or continuous page monitoring.
- Automatic detection before user activation.
- Universal retailer coverage.
- Social, community, publishing, sharing, or public-profile features.
- Automatic checkout across multiple retailers.
- Claims of physical fit or sizing accuracy based only on generated imagery.
- Pretending unsupported accessories appear in a render.

## 16. Open Decisions

### Confirmed implementation baseline

- React and TypeScript Chrome Manifest V3 extension.
- FastAPI backend.
- Pydantic models as the backend contract source, exposed as JSON/OpenAPI
  schemas for TypeScript consumers.
- SQLite for initial private profile and saved-look persistence; generated
  media may use a simple local file store referenced by SQLite.
- Replaceable interfaces for look analysis, catalog providers, retrieval,
  outfit construction, and virtual try-on.
- Single-user, personal-use MVP with no social layer and no hackathon
  requirement for account authentication.

These require discussion or empirical validation before they become source-of-truth decisions.

### Product and UX

1. Extension activation affordance: toolbar only, keyboard shortcut, or both.
2. Confirmation/cropping behavior after drawing the rectangle.
3. Whether Closest is always generated first or the user chooses a mode before spending units.
4. Exact definition of Premium.
5. Result-panel navigation and saved-look structure.

### Catalog and retrieval

1. Initial catalog source and authorization.
2. Initial catalog size and category coverage.
3. Whether to include a live marketplace/search provider.
4. Embedding model and vector-search implementation.
5. Component-level versus outfit-level reranking method.
6. Price and availability refresh strategy.

### VTO and image processing

1. Best order for upper/lower sequential rendering.
2. Product-image compatibility rates by category.
3. Visual drift after multiple sequential stages.
4. Task latency, safe concurrency, retry behavior, and unit cost.
5. How the main result represents shoes and unsupported accessories.

### Platform and data

1. Side-panel state-management and component architecture.
2. Backend hosting and media-storage location for the judged deployment.
3. Storage retention, deletion, and privacy policy.
4. Exact SQLite schema and migration approach.
5. Analytics needed for the hackathon and future product.

## 17. Validation Order

Implementation should reduce the highest-risk assumptions first:

1. Confirm a live YouCam Clothes V3 call with the real API account.
2. Validate one upper-body product image and one lower-body product image.
3. Run a two-stage sequential try-on and visually inspect preservation/drift.
4. Measure latency, unit consumption, and safe concurrency.
5. Validate the rectangular Chrome capture flow over an image and a video frame.
6. Test structured look decomposition on several representative captures.
7. Build and evaluate a small retrieval slice before scaling the catalog.
8. Connect the validated pipeline into the side panel.
9. Add saved looks.
10. Add stretch capabilities only after the complete core loop is stable.

## 18. Decision Discipline

- Confirmed decisions in this document override the earlier ChatGPT handoff and illustrative screenshot.
- The earlier handoff and screenshot remain references, not requirements.
- New assumptions should be recorded under Open Decisions until approved or tested.
- Empirical YouCam behavior should be recorded with the test inputs, endpoint, category, result, latency, units, and date.
- Product language must describe what the system actually demonstrates.
