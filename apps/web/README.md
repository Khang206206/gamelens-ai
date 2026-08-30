# GameLens AI web application

The web application is a Next.js 16.2 App Router project using React 19.2, strict
TypeScript 5.9, and Tailwind CSS 4. It presents the catalog, Stage 3 request-scoped
recommendations, and verified Stage 4 explicit-consent saved-personalization flow. It does
not imply account authentication or cross-device identity.

The detailed
[Stage 4 feedback-and-persistence plan](../../docs/stage-4-feedback-persistence-plan.md)
is complete and verified. Consent, credentialed transport, rehydration, saved preferences,
feedback controls, personalized results, expiry recovery, and clear-data components are
present and fast-tested. The exact-host real-browser persistence, accessibility, and
responsive run plus release review pass.

The detailed
[Stage 5 collaborative-and-hybrid plan](../../docs/stage-5-collaborative-hybrid-ranking-plan.md)
has completed implementation Phases 0–5. The API now exposes additive model-
component status and internally computes lifecycle-aware hybrid/fallback
decisions for saved requests, so the generated client includes the new status
shape. No public personalized hybrid response field, `stage-5-v1` event,
contribution-consent copy, conditional evidence component, or fallback UI exists
yet. The current browser still renders the verified Stage 4 server order and
evidence; those product changes belong to Phase 6.

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
| `/recommendations` | Request-only flow plus opt-in saved state, feedback, and personalized results   |

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

`NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_CONSENT_VERSION` are the browser configuration
boundary. The API URL must be an absolute HTTP(S) URL without credentials, a query string,
or a fragment; trailing slashes are normalized. The consent version defaults to
`stage-4-v1` and must match the API. Next.js embeds these public values into production
client output, so set them before `npm run build`.

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
cancellation. Public calls use `credentials: "omit"`; protected calls use
`credentials: "include"`, `Cache-Control: no-store`, and `X-CSRF-Token` for unsafe
methods. It supports typed `GET`, `POST`, `PUT`, and `DELETE`, including 204 responses,
and maps unauthorized, forbidden, conflict, validation, not-found, unavailable, malformed,
network, abort, and unexpected failures to safe categories while preserving status and
backend error code for application logic.

The request-only recommendation feature keeps selections in component state. It caps game,
genre, tag, and platform choices to the API bounds, requires a content signal, submits
through the shared API client, aborts superseded work, and prevents stale responses from
overwriting current state. The opt-in branch bootstraps `/me`, rehydrates preferences and
feedback after reload, saves bounded preferences, replaces or clears per-game feedback,
generates saved recommendations, and clears all data after confirmation. Credentials and
profile data are not copied into URLs, `localStorage`, or `sessionStorage`. Results stay
in API rank order and scores are not rendered as match percentages.

## Docker workflows

From the repository root, after the explicit migration, seed, model build, and model
validation sequence in the [root README](../../README.md):

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
API and web services. Stage 4 uses the exact host `gamelens.test` for both browser-visible
services: web origin `http://gamelens.test:3000` and API URL `http://gamelens.test:8000`.
The web container shares the API network namespace so both ports resolve to the same
endpoint; consent version, test-only session secret, and insecure test cookie are supplied
explicitly. The locked Playwright 1.62 image can therefore exercise a first-party cookie
over credentialed cross-origin requests across ports rather than a fabricated auth header.
The matrix parses 38 cases: 28 Chromium plus five critical Firefox and five critical
WebKit paths. All 38 pass in 1.3 minutes without retry using two workers.

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

## Stage 4 verification status

The implementation worktree passes 76 Vitest/React Testing Library tests with 67.15%
statement and 71.4% line coverage, strict TypeScript, ESLint, Prettier, and an optimized
production build. The cross-stack evidence also includes 184 fast API tests, 52 ML tests,
and 49 disposable-PostgreSQL integration tests in 4.53 seconds. Production and full npm
audits report zero vulnerabilities; the exact `nanoid@3.3.17` override keeps the PostCSS
dependency path on its patched release. Generated Stage 4 OpenAPI types and credentialed
client tests are present. The 38-case exact-host Playwright matrix covers persistence,
deletion, invalid-cookie recovery, stateless/active axe, full Chromium, and critical
Firefox/WebKit paths. Its re-consent UI case injects an outdated `GET /me` response while
the CSRF-protected `POST` reaches the real current session; real expiry and re-consent
mutation are proven by API/PostgreSQL tests, not claimed as browser evidence. The full
Docker browser run passes 38/38 in 1.3 minutes without retry using two workers. WebKit
active axe includes a real consent `201`; real Origin and CSRF rejection return `403`.
Teardown removes the isolated resources and leaves the Compose process list empty.

The API image used by the full-stack topology removes unused Debian `perl-base` after all
install steps, resolving its earlier two critical and two high findings. The comprehensive
scan of rebuilt no-cache `gamelens-ai-api:stage4-test` image digest prefix `11b2f940731e`
reports 0 critical, 0 high, 3 medium, 27 low, and 2 unspecified findings across 193
packages; its only-fixed scan reports no actionable fixed advisory. Runtime imports,
`pip check`, and all 49 PostgreSQL integration tests remain green. Final release
diff/privacy review is clean.

Stage 5 Phase 5 changes only the generated model-status shape on the web side;
the OpenAPI drift check passes. No Phase 5 browser feature or new web-test count
is claimed. The 76-test web suite and 38/38 browser matrix above remain the
latest product acceptance until Phase 6 adds and verifies the public hybrid
contract and presentation.

## Current limitations

- Saved preferences, feedback, dislike/played adjustment, and recommendation-event logging
  are verified Stage 4 capabilities. The 49-test PostgreSQL, 76-test web, and 38/38
  exact-host browser gates are green.
- The anonymous credential is same-device/browser only. There are no accounts,
  cross-device recovery, or background retention guarantees.
- The synthetic 30-game fixture verifies functionality and reproducibility, not
  recommendation quality; formal evaluation remains Stage 6.
- Stage 5 Phase 5 loader/readiness/lifecycle/internal orchestration is complete,
  but public personalized hybrid response/event fields and conditional browser
  evidence are Phase 6 work. The browser currently exposes only Stage 3/4
  personalized ranking fields and does not sort or recompute server results.
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
