# WANT!

A private Chrome side-panel app that captures an outfit, finds current buyable
matches, previews selected apparel on the user's photo, and saves the result
locally.

## How it works

```text
Chrome side panel
    -> FastAPI receives the selected image
    -> OpenAI inventories every visible wearable
    -> one concurrent live shopping search runs per item
    -> the user chooses one real product per row
    -> YouCam Clothes V3 renders the supported selections
    -> SQLite and local media store the private saved look
```

OpenAI handles understanding and live product discovery; it does not generate
the try-on. YouCam Clothes V3 is the visible rendering step and receives the
exact products selected in the side panel.

## Run locally

Prerequisites: Python 3.12, `uv`, Node.js, `pnpm`, and Chrome 116 or newer.

1. Put the provider keys in `.env`:

   ```text
   OPENAI_API_KEY=...
   YOUCAM_API_KEY=...
   ```

2. Install and build:

   ```bash
   uv sync
   pnpm install
   pnpm build
   ```

3. Start the API:

   ```bash
   uv run uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
   ```

4. Open `chrome://extensions`, enable **Developer mode**, choose **Load
   unpacked**, and select `apps/extension/dist`.

5. Open WANT! from the toolbar and choose a full-body photo.

6. Chrome asks for persistent site access in a packaged/Web Store installation.
   Development extensions loaded with **Load unpacked** do not show the normal
   consumer installation prompt; Chrome reads the required `<all_urls>` grant
   directly from the manifest. WANT! uses it only after **Pick a look** to inject
   the selection overlay and capture the chosen rectangle. When the selection is
   mostly one page image, WANT! crops its original-resolution asset; otherwise it
   falls back to a cursor-hidden visible-tab screenshot. Chrome internal
   pages, the Chrome Web Store, and browser settings pages remain restricted.

Press **Alt+W** on a regular webpage to open WANT!, then press **Pick a look**.
The shortcut can be changed at `chrome://extensions/shortcuts`.

Re-run `pnpm build` and reload the extension after frontend changes. The API
reload command for development is:

```bash
uv run uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Verify

```bash
uv run ruff check apps tests
uv run pytest -q
pnpm typecheck
pnpm build
```

## Code map

- `apps/extension/src/background.ts` opens the side panel, injects capture mode,
  and stores a pending capture while the panel opens.
- `apps/extension/src/content.ts` owns the on-page drag-selection overlay.
- `apps/extension/src/sidepanel/capture.ts` turns the selected rectangle into a
  crop, preferring the original page image when possible.
- `apps/extension/src/sidepanel/main.tsx` contains the side-panel screens and
  user flow; `api.ts` is its only backend client and `types.ts` mirrors the API.
- `apps/api/app/main.py` wires the FastAPI routes and process-lifetime services.
- `openai_discovery.py`, `openai_prompts.py`, and `look_builder.py` inventory,
  search, normalize, crop, and assemble each product row.
- `try_on.py` validates the chosen ranks and sequences supported garment regions
  through `youcam.py`.
- `database.py` and `media.py` store the local profile, saved snapshots, captures,
  and final YouCam images.
- `contracts.py` is the shared backend data contract; `tests/` protects API,
  normalization, selection, and YouCam behavior.

The detailed product boundary lives in `docs/product-spec.md`; the accepted
agentic runtime and measured provider results live in `docs/agentic-plan.md`.

Personal photos, captures, provider payloads, and generated images remain under
ignored `private-input/` and `private-output/` directories. API keys are never
bundled into the extension.

The runtime uses OpenAI visual inventory plus concurrent hosted image/text
shopping, then sends the user's arrow-selected product combination to YouCam
Clothes V3. There is no fallback provider, local product catalogue or local
vector/embedding search path.

## Current product boundary

The implemented path returns one evidence-backed **Closest** outfit with up to
three options per item. There are no alternate price tiers. Product/image URLs
come directly from the OpenAI response without a second HTTP check or image
cache. Known prices keep their listed currencies; a total appears only when all
selected known prices share one currency. SQLite is retained only for the
profile and Saved Looks.
