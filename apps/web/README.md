# GameLens AI web application

The Stage 3 web application is a Next.js 16.2 App Router project using React 19.2, strict
TypeScript 5.9, and Tailwind CSS 4. It presents the catalog plus real artifact-backed,
request-scoped recommendations without implying persisted preferences, feedback, or
authentication.

The detailed
[Stage 4 feedback-and-persistence plan](../../docs/stage-4-feedback-persistence-plan.md)
is ready; implementation has not started. The current browser still creates no identity,
sends no credentialed persistence request, and stores no onboarding or feedback state
across reloads.

## Responsibilities

The browser dependency direction is:

```text
route -> feature component -> project API client -> FastAPI
```

`src/app` owns routes and framework boundaries, `src/features` owns catalog and detail
behavior, `src/components` owns reusable presentation, and `src/lib/api` is the only
browser path to FastAPI. The application does not connect to PostgreSQL, contain backend
credentials, proxy requests through Next.js, or rank games.

## Routes

| Route              | Implemented behavior                                                            |
| ------------------ | ------------------------------------------------------------------------------- |
| `/`                | Server-rendered product introduction and catalog call to action                 |
| `/games`           | URL-backed title search, one genre/tag/platform filter, sorting, and pagination |
| `/games/[gameId]`  | Numeric-ID game details with explicit nullable-field states                     |
| `/recommendations` | Accessible select, review, and explained-results flow                           |

Catalog state uses `q`, `genre`, `tag`, `platform`, `sort`, and `page` search parameters.
The runtime parser rejects malformed values before an API request, while reload,
back/forward navigation, bookmarks, and shared links reproduce valid state.

## Direct npm workflow

First start, migrate, seed, and expose the API from the repository root. Then:

```powershell
Set-Location apps/web
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Open `http://localhost:3000`. The ignored `.env.local` is for direct npm work; the root
`.env` remains the Docker Compose source.

`NEXT_PUBLIC_API_URL` is the only required browser variable. It must be an absolute
HTTP(S) URL without credentials, a query string, or a fragment. Trailing slashes are
normalized. Next.js embeds this public value into production client output, so set it
before `npm run build`.

## Commands

Run commands from `apps/web`:

| Command                                   | Purpose                                                          |
| ----------------------------------------- | ---------------------------------------------------------------- |
| `npm run dev`                             | Start the development server                                     |
| `npm run build` / `npm run start`         | Build or serve the production bundle                             |
| `npm run typecheck`                       | Run strict TypeScript without emitting files                     |
| `npm run lint`                            | Run ESLint                                                       |
| `npm run format` / `npm run format:check` | Apply or verify Prettier formatting                              |
| `npm run test`                            | Run Vitest and React Testing Library checks                      |
| `npm run test:coverage`                   | Run fast tests with diagnostic V8 coverage                       |
| `npm run playwright:install`              | Install locked host Chromium, Firefox, and WebKit binaries       |
| `npm run test:e2e`                        | Run Playwright against `WEB_BASE_URL` or `http://localhost:3000` |
| `npm run api:types`                       | Refresh committed TypeScript contracts from the live API         |
| `npm run api:types:check`                 | Fail when the live OpenAPI contract and generated output differ  |
| `npm audit --omit=dev`                    | Audit the production dependency tree                             |
| `npm audit`                               | Audit production and development dependencies                    |

Type generation reads `OPENAPI_URL` when supplied, otherwise
`${NEXT_PUBLIC_API_URL}/openapi.json`, defaulting to the documented local API. The scripts
load `.env.local` with Next's environment loader and apply a 15-second request timeout.
Set `OPENAPI_TIMEOUT_MS` to a whole number from 1000 through 120000 only when a trusted
endpoint needs a different bound. The generated file is committed at
`src/lib/api/generated.ts`; feature code must not hand-copy backend response interfaces.

The client validates JSON content, the standard error envelope, HTTP status, and
cancellation. It maps validation, not-found, unavailable, malformed, network, abort, and
unexpected failures to safe categories while preserving status and backend error code for
application logic.

The recommendation feature keeps selections in component state only. It caps game, genre,
tag, and platform choices to the API bounds, requires a content signal, submits through
the shared API client, aborts superseded work, and prevents stale responses from
overwriting current state. Results remain in API rank order and expose ranking score,
structured reasons, and component details. The score is deliberately not rendered as a
match percentage.

## Docker workflows

From the repository root, after the explicit migration, seed, model build, and
model validation sequence in the [root README](../../README.md):

```powershell
docker compose build web
docker compose up -d db api web
docker compose ps
```

Windows source files are bind-mounted at `/workspace`; named `web_node_modules` and
`web_next` volumes keep Linux dependencies and Next.js cache out of the host tree. At
startup, a constrained initializer compares the bind-mounted lockfile with the image
lockfile. A stale image fails with a rebuild instruction. A stale or root-owned dependency
volume is synchronized from the image, ownership is repaired, and the disposable Next.js
cache is cleared when dependencies change. The initializer then drops to the non-root
`node` user before starting Next.js. It does not install from the network at runtime.

The published web port binds to `127.0.0.1` and defaults to `WEB_PORT=3000`. If that port
changes, update `CORS_ORIGINS` to the same web origin. If `API_PORT` changes, update
`NEXT_PUBLIC_API_URL` to the same API origin. Web startup never migrates, seeds, resets,
or deletes the database.

The browser acceptance stack is isolated:

```powershell
$e2eExitCode = 0
try {
    docker compose -f infra/docker-compose.e2e.yml up --build `
        --abort-on-container-exit --exit-code-from e2e e2e
    $e2eExitCode = $LASTEXITCODE
} finally {
    docker compose -f infra/docker-compose.e2e.yml down --volumes --remove-orphans
}
if ($e2eExitCode -ne 0) { exit $e2eExitCode }
```

It creates a tmpfs PostgreSQL database, migrates and seeds it in an explicit setup
service, initializes a disposable named artifact volume, builds the Stage 3 model as the
non-root application user, mounts it read-only in the API, and then starts network-only
API and web services. The locked Playwright 1.62 image runs the complete Chromium suite
and critical Firefox/WebKit smoke paths against the deterministic 30-game catalog. E2E
teardown removes only this isolated project's containers, network, and artifact volume.

## Verified Stage 3 quality

The acceptance gate on 2026-08-07 produced:

- 45 fast tests across query parsing, formatting, configuration, API errors, request
  transport, shared UI, truthful landing content, and the recommendation flow.
- Strict TypeScript, ESLint, Prettier, clean install, OpenAPI drift, and production build
  passes.
- Targeted npm overrides resolve Next.js to PostCSS 8.5.25 and Sharp 0.35.3, `js-yaml` to
  4.3.1, and each `brace-expansion` consumer to its fixed patch line. Clean install plus
  full and production audits report zero vulnerabilities.
- 25 Playwright passes without retry: 15 complete Chromium tests and five critical smoke
  tests in each of Firefox and WebKit.
- No serious or critical axe violations on landing, populated catalog/detail,
  recommendation results, invalid-ID, and 404 states.
- Mobile primary navigation is visible and keyboard reachable. Catalog, detail, and
  recommendation routes have no horizontal page overflow at 320, 768, or 1440 CSS pixels.
- Diagnostic V8 coverage of 53.25% statements overall; the recommendation flow reports
  77.51%. Real-browser tests remain the primary catalog/detail workflow coverage.

## Current limitations

- Onboarding selections and results are not persisted. Durable preferences, feedback,
  dislike/played adjustment, and recommendation-event logging are specified by the
  [Stage 4 engineering plan](../../docs/stage-4-feedback-persistence-plan.md) but are not
  implemented.
- The synthetic 30-game fixture verifies functionality and reproducibility, not
  recommendation quality; formal evaluation remains Stage 6.
- The deterministic catalog has no cover binaries or approved remote image source, so
  every game uses a project-owned generated placeholder.
- Ratings and popularity are synthetic development signals, not market data or
  recommendation evidence.
- Production deployment, optimized production containers, monitoring, and CI remain Stage
  7 work. The current localhost `metadataBase` is development-only; Stage 7 must supply a
  validated public site origin.
- Malformed game IDs use the route-specific not-found boundary, and well-formed numeric
  IDs missing from the API use a client not-found state. The streamed dynamic route shell
  returns HTTP 200 in both cases. The missing-ID API response remains 404; true
  server-route status propagation requires the later internal-origin/deployment design.
