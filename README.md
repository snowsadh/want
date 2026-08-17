<p align="center">
  <img src="apps/extension/public/wordmark.png" width="300" alt="WANT!">
</p>

<p align="center"><strong>From “I want that” to “that’s me in it.”</strong></p>

<p align="center">
  WANT! turns any outfit you spot online into a shoppable look you can try on yourself—without leaving the page that inspired you.
</p>

<p align="center">
  Built for the <a href="https://youcam-api.devpost.com/">YouCam API Skin AI &amp; Apparel VTO Hackathon</a>
  using <strong>YouCam Clothes V3</strong>.
</p>

<table>
  <tr>
    <td align="center"><img src="apps/extension/public/onboarding/grab.png" width="230" alt="Grab an outfit from anywhere on the web"></td>
    <td align="center"><img src="apps/extension/public/onboarding/try.png" width="230" alt="Try the selected outfit on yourself"></td>
    <td align="center"><img src="apps/extension/public/onboarding/get.png" width="230" alt="Get the real products in the outfit"></td>
  </tr>
  <tr>
    <td align="center"><strong>Grab the look</strong><br>Box an outfit on any page or upload an image.</td>
    <td align="center"><strong>Try it on</strong><br>See the selected clothing on your own photo.</td>
    <td align="center"><strong>Get the outfit</strong><br>Open real products directly at their stores.</td>
  </tr>
</table>

## The internet is the inspiration. WANT! is the fitting room.

Great outfits rarely appear as tidy product listings. They show up in videos,
posts, editorials, and street-style photos—usually with no useful way to find
the complete look, much less see it on yourself.

WANT! closes that gap in one continuous experience:

1. **Capture what caught your eye.** Press **Alt+W**, choose **Pick a look**,
   and draw around an outfit on the page. You can also upload a screenshot.
2. **Discover the whole outfit.** WANT! identifies every visible wearable and
   finds current, buyable matches for each piece—not just the easiest item.
3. **Build your closest recreation.** Browse up to three strong options in each
   product row and select the combination that feels right.
4. **See it on you.** YouCam Clothes V3 renders supported apparel on your photo,
   carrying earlier garment stages forward as the outfit comes together.
5. **Get it or keep it.** Open any product at its retailer, or save the finished
   look to your private collection—with you as the model.

## Why WANT! feels different

- **It understands looks, not isolated products.** A reference becomes a
  complete inventory of clothing, shoes, jewelry, and accessories.
- **Discovery and try-on stay connected.** The exact products you choose are
  the products sent into the YouCam rendering flow.
- **Every result leads somewhere useful.** Product cards preserve real images,
  listed prices, and direct retailer links wherever a credible match exists.
- **The preview stays honest.** Pieces that YouCam did not render remain
  shoppable in the look tray and are clearly marked as not shown in the preview.
- **Your photos stay yours.** Profiles, captures, generated images, and saved
  looks live in private local storage rather than a public feed.

## More than a single API call

WANT! uses an agentic shopping workflow to bridge inspiration and purchase:

```text
outfit selected anywhere on the web
    -> OpenAI inventories every visible wearable
    -> concurrent live shopping runs for each distinct item
    -> reachable product images and purchase links are preserved
    -> the user chooses one coherent combination
    -> YouCam Clothes V3 renders the supported selections
    -> the finished look and its products can be saved privately
```

OpenAI handles visual understanding and live product discovery. **YouCam is the
fitting room:** it is the visible, product-defining step that turns a list of
matches into a personalized buying decision.

## Try WANT!

WANT! runs as a Firefox desktop sidebar with a local FastAPI service.

### Requirements

- Firefox 142 or newer
- Python 3.12 and [`uv`](https://docs.astral.sh/uv/)
- Node.js and [`pnpm`](https://pnpm.io/)
- OpenAI and YouCam API keys

### 1. Configure the providers

Create `.env` at the repository root:

```text
OPENAI_API_KEY=...
YOUCAM_API_KEY=...
```

The keys remain in the local server environment and are never bundled into the
extension.

### 2. Install and build

```bash
uv sync
pnpm install
pnpm build
```

### 3. Start the local API

```bash
uv run uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
```

### 4. Load the Firefox extension

1. Open `about:debugging#/runtime/this-firefox`.
2. Select **Load Temporary Add-on**.
3. Choose `apps/extension/dist/manifest.json`.
4. Open WANT! from the toolbar and add a full-body photo.
5. Visit a page with an outfit, press **Alt+W**, and choose **Pick a look**.

The shortcut can be changed in `about:addons` under **Manage Extension
Shortcuts**.

## Privacy by design

WANT! acts only after a deliberate capture, upload, search, or try-on action.
Personal photos, captures, provider payloads, and generated images are stored in
ignored local `private-input/` and `private-output/` directories. Saved Looks
and the local profile use SQLite. Read the full [privacy
policy](docs/privacy-policy.md) for data handling and provider details.

<details>
<summary><strong>Development and code map</strong></summary>

### Development server

```bash
uv run uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Re-run `pnpm build` and reload the temporary add-on after frontend changes.

### Verification

```bash
uv run ruff check apps tests
uv run pytest -q
pnpm typecheck
pnpm build
```

### Repository map

- `apps/extension/src/background.ts` opens the sidebar, activates capture mode,
  and carries a pending capture into the panel.
- `apps/extension/src/content.ts` owns the on-page drag-selection experience.
- `apps/extension/src/sidepanel/capture.ts` crops the selection, preferring the
  original page image when possible.
- `apps/extension/src/sidepanel/main.tsx` contains the sidebar screens and
  product flow; `api.ts` is its backend client and `types.ts` mirrors the API.
- `apps/api/app/main.py` wires the FastAPI routes and process-lifetime services.
- `openai_discovery.py`, `openai_prompts.py`, and `look_builder.py` inventory,
  search, normalize, validate product images, and assemble each product row.
- `try_on.py` validates the selected products and sequences supported garment
  regions through `youcam.py`.
- `database.py` and `media.py` store the local profile, saved looks, captures,
  product media, and final YouCam images.
- `contracts.py` defines the backend data contract; `tests/` protects API,
  normalization, selection, and YouCam behavior.

The detailed product behavior lives in
[`docs/product-spec.md`](docs/product-spec.md). The accepted agentic runtime and
provider evaluation live in [`docs/agentic-plan.md`](docs/agentic-plan.md).

</details>
