# WANT!

A private Chrome side-panel app that captures an outfit, finds current buyable
matches, previews selected apparel on the user's photo, and saves the result
locally.

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
