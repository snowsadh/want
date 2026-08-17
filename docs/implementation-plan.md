# WANT! — Remaining Demo Plan

> The OpenAI-to-YouCam vertical slice is implemented. Only demo verification and
> presentation work remains.

## Current architecture

```text
Firefox MV3 sidebar
    -> FastAPI modular monolith
    -> OpenAI visual inventory
    -> concurrent OpenAI image + text shopping
    -> arrow-selected product combination
    -> YouCam Clothes V3
    -> SQLite saved looks + local media
```

The five-reference provider gate passed with 30 detected items, 38 products,
two fallbacks, 34.7 seconds mean latency and 49.1 seconds maximum latency. A
remote returned product URL also completed a real YouCam render in 43.3 seconds.

## Existing API

```text
GET    /api/health
GET    /api/profile
PUT    /api/profile
POST   /api/profile/photo
POST   /api/looks
POST   /api/try-ons
GET    /api/try-ons/{job_id}
POST   /api/saved-looks
GET    /api/saved-looks
GET    /api/saved-looks/{saved_id}
DELETE /api/saved-looks/{saved_id}
```

Do not add endpoints for the hackathon demo.

## Remaining work

### Browser verification

- Reload `apps/extension/dist` in the actual demo Firefox profile.
- Verify toolbar click and `Alt+W` capture on a normal image and paused video.
- Verify cancel uploads nothing and screenshot fallback selects the right area.
- Confirm every detected item gets one row and arrows wrap through its options.
- Confirm changing an option clears an older try-on preview.

### End-to-end rehearsal

- One clean capture-to-saved-YouCam run passed on 2026-08-17.
- Upload the final demo full-body photo.
- Run the chosen reference from capture through **Try this look** and Save.
- Confirm the selected ranks—not merely rank one—reach YouCam and the saved look.
- Confirm unsupported accessories remain links and are not labelled rendered.
- Complete two more consecutive clean runs inside 1–3 minutes.

### Submission

- Check Git and built extension assets for secrets/private outputs.
- Record the demo and screenshots with the YouCam transformation visible.
- Document setup, the agentic item searches and YouCam's contribution.

## Verification commands

```bash
uv run ruff check apps tests
uv run pytest -q
pnpm typecheck
pnpm build
```

## Deferred

Delivery filtering, product-page revalidation, accessory VTO, authentication,
social features, a product database, vector search, scrapers,
Redis, queues, workers and extra services remain out of scope unless a measured
demo failure requires one.
