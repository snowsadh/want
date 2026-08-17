# WANT! — Remaining Demo Plan

> The hosted-processing refactor is implemented. Only deployment, judge-package
> publication and submission presentation remain.

## Current architecture

```text
Chrome side panel or Firefox sidebar
    -> browser IndexedDB owns the profile and saved wardrobe
    -> hosted FastAPI processing service
    -> OpenAI visual inventory
    -> concurrent OpenAI image + text shopping
    -> browser-local copy of validated evidence
    -> user-selected product images + person photo uploaded for the task
    -> YouCam Clothes V3
    -> final image copied back into IndexedDB
```

The five-reference provider gate passed with 30 detected items, 38 products,
two fallbacks, 34.7 seconds mean latency and 49.1 seconds maximum latency. A
real YouCam render completed in 43.3 seconds.

## Processing API

```text
GET  /api/health
POST /api/looks
POST /api/try-ons
GET  /api/try-ons/{job_id}
```

The API has no profile or saved-look endpoints. Browser IndexedDB owns durable
user state; FastAPI owns provider credentials and short-lived task media.

## Completed technical work

- FastAPI is deployed to Railway with serverless sleeping and server-side
  OpenAI and YouCam credentials.
- Chrome and Firefox build from one extension source against a configurable API
  origin.
- macOS and Windows Chrome installers are packaged for the judge page.
- The API suite, Ruff, TypeScript checks, both browser builds and all judge ZIPs
  pass verification.

## Remaining work

- Publish the judge page from the GitHub Pages workflow.
- Run each installer on its native operating system when those machines are
  available.

### Submission

- Record the 1–3 minute demo with the YouCam transformation visible.
- Add the final product screenshots to the README and Devpost submission.
- Verify the public repository and packaged extension contain no provider keys,
  personal photos, private captures, or generated outputs.

## Verification commands

```bash
uv run ruff check apps tests
uv run pytest -q
pnpm typecheck
pnpm build
```

## Deferred

Account sync, delivery filtering, accessory VTO, social features, a product
database, vector search, scrapers, Redis, queues and distributed workers remain
outside the hackathon MVP.
