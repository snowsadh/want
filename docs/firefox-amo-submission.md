# Firefox AMO Submission

## Upload

- Distribution: **On this site** (listed on AMO)
- Platform: **Firefox desktop**
- Category: **Shopping**
- Requires non-free services: **Yes** (OpenAI and YouCam API access)
- Privacy policy: `https://github.com/snowsadh/want/blob/firefox/docs/privacy-policy.md`

Upload the extension ZIP and source ZIP generated under
`private-output/firefox-release/`.

## Listing copy

Summary:

> Capture an outfit from any webpage, find real products, and preview supported apparel with YouCam.

Description:

> WANT! lets you draw around an outfit on a webpage or upload a reference image. It identifies each visible wearable, finds current retail matches, lets you choose one product per item, and uses YouCam Clothes V3 to preview supported apparel on your uploaded full-body photo. Product links and saved looks remain in your local WANT! installation.

## Notes for reviewers

WANT! transmits data only after deliberate user actions. **WANT! this look**
sends the selected image and source URL to the user-operated local API, which
uses OpenAI for apparel inventory and product discovery. **Try it on** sends the
user-provided full-body photo and supported selected garment images to Perfect
Corp.'s YouCam Clothes V3 API. There is no analytics, advertising, passive
browsing collection, or remote executable code.

The broad host permission lets the extension capture a user-drawn region on any
normal webpage and, when possible, download the explicitly selected source image
at its original resolution. Browser-owned pages remain inaccessible.

The two `innerHTML` warnings from `web-ext lint` originate in the bundled,
unmodified React DOM 19 runtime. WANT!'s source does not use `innerHTML` or
`dangerouslySetInnerHTML`. Third-party packages are installed from the official
npm registry using the committed `pnpm-lock.yaml`.

For full functional testing, provide temporary OpenAI and YouCam credentials in
AMO's private reviewer notes or give reviewers access to a temporary judge API.
Never include those credentials in either uploaded archive.

## Reproduce the extension build

The submitted build was produced on Linux with Node.js 26.7.0 and pnpm 10.30.2:

```bash
pnpm install --frozen-lockfile
pnpm build
```

The extension output is `apps/extension/dist`. The API is not required to
reproduce the extension package. To exercise the complete product locally, add
`OPENAI_API_KEY` and `YOUCAM_API_KEY` to `.env`, then run:

```bash
uv sync
uv run uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
```
