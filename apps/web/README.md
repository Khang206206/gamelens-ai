# Web application

**Status:** The Stage 2 engineering plan is ready; application implementation
has not started. The Stage 1 backend handoff is complete, and this directory
remains reserved for the Next.js and TypeScript application.

See the
[Stage 2 frontend engineering plan](../../docs/stage-2-frontend-foundation-plan.md)
for scope, phases, verification, acceptance criteria, risks, and the Stage 3
handoff.

## Planned responsibility

The frontend will own routes, presentation components, browser state, and a
typed API client. It will use environment-based API configuration, responsive
and accessible components, URL-backed catalog state, and explicit loading,
empty, not-found, partial-error, and full-error states.

It will not connect to PostgreSQL, embed backend secrets, implement ranking,
or fabricate recommendations while the backend model status is
`not_configured`.

## Target routes

| Route | Planned purpose |
| --- | --- |
| `/` | Truthful product introduction and catalog call to action |
| `/games` | Search, single-value taxonomy filters, sorting, and pagination |
| `/games/[gameId]` | Details through the existing numeric game ID contract |

Search, filters, sort, and page will be encoded in the catalog URL so reload,
browser history, bookmarks, and shared links reproduce the same request.

## Stage 1 API handoff

The verified local backend contract available to Stage 2 includes:

- API base URL `http://localhost:8000`, configurable for the browser through
  `NEXT_PUBLIC_API_URL`.
- OpenAPI at `/openapi.json` and interactive documentation at `/docs`.
- Paginated catalog, game detail, and sorted genre, tag, and platform routes
  under `/api/v1`.
- One-based pages with a default size of 20 and a maximum size of 100.
- Title search and genre, tag, and platform filters plus deterministic catalog
  sorting.
- A consistent error envelope for validation, not-found, database, and
  unexpected failures.
- An explicit `not_configured` model status; Stage 2 must not present
  recommendations as available yet.

The synthetic catalog currently has no cover-image URLs. Stage 2 will provide
a project-owned placeholder and will not introduce an undocumented remote
image source.

The default CORS allowlist contains `http://localhost:3000`. If the Stage 2
development origin changes, update `CORS_ORIGINS` in the ignored root `.env`
file rather than hard-coding an origin in frontend or backend code.

The planned direct npm workflow will use an ignored `apps/web/.env.local`
created from an app-local example; the root `.env` will remain the Compose
source. Public API values must be supplied before a production build because
Next.js embeds `NEXT_PUBLIC_` values into the client bundle.

## Current command status

No npm, Next.js, web-container, or frontend quality command exists yet.
Commands will be documented here only after the corresponding Stage 2
implementation has been created and verified.
