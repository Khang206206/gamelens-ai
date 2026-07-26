# Web application

**Status:** Stage 2 has not started. The Stage 1 backend handoff is complete,
and this directory remains reserved for the Next.js and TypeScript
application.

The frontend will use typed API models, environment-based API configuration,
responsive and accessible components, and explicit loading, empty, and error
states.

The verified local backend contract available to Stage 2 includes:

- API base URL `http://localhost:8000`, configurable for the browser through
  `NEXT_PUBLIC_API_URL`.
- OpenAPI at `/openapi.json` and interactive documentation at `/docs`.
- Paginated catalog, game detail, and sorted genre, tag, and platform routes
  under `/api/v1`.
- One-based pages with a default size of 20 and a maximum size of 100.
- Search and genre, tag, and platform filters plus deterministic catalog
  sorting.
- A consistent error envelope for validation, not-found, database, and
  unexpected failures.
- An explicit `not_configured` model status; Stage 2 must not present
  recommendations as available yet.

The default CORS allowlist contains `http://localhost:3000`. If the Stage 2
development origin changes, update `CORS_ORIGINS` in the ignored root `.env`
file rather than hard-coding an origin in frontend or backend code.
