# WANT! — UI/UX Direction

> Working design brief and decision log. Last updated 2026-08-16.

## Experience north star

WANT! should feel like a polished personal styling experience where the user is
always the model. It is not a conventional shopping catalogue, a developer
utility or a toy dress-up game.

The interaction may borrow the immediacy and visual clarity of a game, but the
finish must communicate that the product links, saved looks and YouCam preview
are dependable. The target feeling is **playful selection with credible
execution**.

```text
grab a look from anywhere
    -> find and choose real buyable pieces
    -> try the supported outfit on yourself with YouCam
    -> get any piece from its retailer
    -> save the look with yourself as the model
```

## Three product promises

The first-run onboarding uses three cleanly separated illustrations. Each frame
communicates one promise without explaining the implementation:

1. **Grab a look from anywhere.** Capture a look on the web or upload an image.
2. **Try it on yourself.** See the supported selected garments on the user's
   full-body photo through YouCam.
3. **Get the outfit.** Open the real retailer page for any matched piece.

The illustrations should form one visual story and remain understandable with
little or no supporting copy.

## Agreed product flow

### Entry and home

`Alt+W` opens a small launcher with three clear destinations:

- capture a look from the current page;
- upload an image;
- open **Me**.

After a capture or upload, the user confirms the image and starts discovery
with one primary WANT! action. The final action label can be refined during the
copy pass, but it must describe the result rather than the technology.

### Processing

Discovery gets an intentional animated state instead of a generic spinner.
While WANT! inventories and shops for the pieces, it may show short useful tips
or plainly worded progress. Motion should make the wait feel active without
pretending the result is ready or inventing progress percentages.

### Outfit builder

Results are image-first and low on text. Each detected item gets a visual row
of up to three choices, with the active choice unmistakably highlighted. Rank
one remains selected by default. Changing a choice updates the assembled
combination and invalidates an older try-on preview.

The builder should feel as immediate as choosing equipment in a game, while
avoiding game-themed chrome, novelty language or excessive animation.

Primary actions are:

- **Try it** for the exact selected YouCam-supported combination;
- **Save it** for the current selection;
- **Get it** for an individual real product.

### Try view

The YouCam result is the hero: a large image of the user wearing the rendered
garments. A compact clothing tray shows every selected piece, including
shopping-only accessories or layers that are part of the look but were not
rendered.

Rendered and shopping-only items must be visually distinct and truthfully
labelled. The view provides:

- Get It access for every matched product;
- a small unfilled heart to save, which fills after saving;
- Try another combination;
- Home.

### Me and Saved

**Me** contains the user's photo, profile information and Saved Looks. Saved
looks use an image-first grid similar to a fashion-commerce collection, except
the user is the model in every personalized result. Opening a saved tile returns
to the same Try view rather than a separate read-only design.

## Get It interaction

Direct access to real product pages is one of WANT!'s core differentiators and
must be obvious in both the outfit builder and Try view.

- Clicking a carousel tile selects it; the compact retailer row and arrow open
  the direct product page.
- Try-view product tiles open their retailer page and retain keyboard focus.
- Retailer and known price remain visible but secondary.
- Unmatched original-piece fallbacks never display Get It.

The same wording and visual treatment must be used everywhere so the action is
learned once.

## Visual identity direction

The selected direction is an evolution of the current light, high-contrast WANT!
interface, informed by the **Digital Atelier** exploration. This is a refinement,
not a wholesale rebrand. The dark Editorial Flash and catalog-like Wardrobe
Archive explorations were rejected as generic and less characteristic of WANT!.

Preserve the bold wordmark, light canvas, cobalt interaction color, image-first
product treatment and capture-frame character. Improve perceived quality through
typography, spacing, consistent depth, precise borders, richer interaction states
and restrained atelier details such as capture corners, pattern marks and mirror
geometry.

The implemented foundation returns to the repository-original WANT! system:
cool paper (`#F7F8FC`), near-black ink (`#17191C`), cobalt (`#315CFF`) and the
original pink accent (`#FF4F70`), with hard offset shadows and square capture
geometry. **Archivo** is the display face, paired with **Manrope** and
**Space Mono**. This supersedes the softer Digital Atelier restyling while
retaining its improved product flow.
The implementation does not inherit every decorative element from the generated
concept mockup.

The selected system must:

- feel native to personal style, clothing and mirrors rather than generic AI;
- give photography and clothing cutouts priority over interface decoration;
- stay expressive enough for WANT!'s name and capture interaction;
- feel trustworthy beside real prices, retailer links and generated previews;
- remain legible and composed in a narrow Firefox sidebar.

Removing the person's background is deferred. Preserve the original photo and
YouCam result in the UI for the MVP.

## Trust, shadows and finishing

Polish is a product requirement, not a final decorative pass.

- Use the original authored hard-offset depth system consistently across panels,
  actions and product tiles. Avoid mixing it with unrelated soft elevation.
- Reserve the strongest depth or contrast for the current primary action.
- Align image crops, baselines, corner treatments and optical spacing with care.
- Define hover, pressed, selected, loading, success, empty, unavailable and
  keyboard-focus states for every interactive component.
- Keep motion short and purposeful; respect reduced-motion preferences.
- Use skeletons or staged item reveals only when they reflect real system state.
- Product links should look safe and intentional before the hover interaction,
  with retailer identity and an external-link cue available at rest.
- Use honest language for unmatched products and items not included in the
  YouCam render.

The guiding distinction is: **game-like responsiveness, not toy-like styling**.

## Profile and storage direction

Email/account support is desirable after publication because cloud-backed saved
looks allow sync across devices. It is not required for the hackathon flow.

For the current MVP:

- keep the existing local profile, local media, SQLite and local Saved Looks;
- do not imply that an email address creates cloud sync when it does not;
- email may be omitted or stored only as clearly local profile metadata.

Post-hackathon:

- add real sign-up/authentication and cloud storage together;
- migrate or offer to upload local saved looks after the user signs in;
- preserve a local-only option if privacy remains part of the product promise.

## Implementation roadmap

1. Lock navigation, screen hierarchy and action vocabulary.
2. Explore and select the narrative-led color, type, depth and motion system.
3. Design the three-illustration onboarding.
4. Redesign the Alt+W launcher and Me surface.
5. Create the processing animation and rotating-tip system.
6. Redesign results as the image-first outfit builder.
7. Make the YouCam Try view the visual payoff.
8. Build Saved as the user's personal lookbook.
9. Add complete interaction states, accessibility and responsive behavior.
10. Rehearse and polish the complete 1–3 minute judged demo.

### 2026-08-16 implementation pass

The first coherent frontend pass now includes the three-step Digital Atelier
onboarding, photo setup, capture/upload/Me launcher, animated discovery with
honest tips, a clean three-option depth carousel whose selected tile moves into
a larger, brighter center plane, compact retailer links, the
person-first YouCam result, shopping-only garment labels, heart saving, and a
local Saved Looks grid. Remaining work is demo rehearsal, content QA with the
fixed references, and any small polish discovered during that rehearsal.

## MVP guardrails

- YouCam Clothes V3 remains a real, visible and meaningful centerpiece.
- Get It always opens a real direct product page; it never implies checkout
  inside WANT!.
- Accessories and unsupported layers may remain shoppable but are never claimed
  to appear in the preview unless rendered and verified.
- One Closest combination is assembled from the user's selected products.
- No social feed, public profile, sharing or fake pricing tiers.
- Known prices retain their listed currency; missing prices are not invented.
