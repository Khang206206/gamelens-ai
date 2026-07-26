# GameLens AI

## Stage 2 Engineering Plan: Frontend Foundation

- **Document status:** Ready for implementation as of 2026-07-26; no Stage 2
  application code has been added yet.
- **Stage 1 prerequisite:** Complete and verified.
- **Target branch:** `feat/stage-2-frontend-foundation`
- **Primary outcome:** A runnable, tested, responsive, and accessible Next.js
  catalog experience backed by the verified Stage 1 API.

This document intentionally uses forward-looking implementation language.
Implementation-time decisions must be recorded in Section 21, the Stage 3
handoff must be updated in Section 22, and completion evidence must be added to
Section 23 only after the complete acceptance gate passes.

## 1. Context

Stage 1 established a stable FastAPI and PostgreSQL catalog slice with
deterministic development data, documented OpenAPI contracts, explicit CORS
configuration, and reliable Docker workflows. Stage 2 turns that backend
handoff into the first user-facing application.

The executable contract and local workflow are documented in the
[API README](../apps/api/README.md), and the completed prerequisite is recorded
in the [Stage 1 engineering plan](stage-1-backend-database-plan.md).

The frontend must stay inside the capabilities that actually exist. Users can
browse, search, filter, sort, paginate, and inspect game details. They cannot
submit preferences, receive recommendations, record feedback, or authenticate
until later stages add the required API contracts.

The resulting frontend should demonstrate:

- A clear boundary between routes, feature components, shared UI, and API
  access.
- Type-safe consumption of the machine-readable Stage 1 OpenAPI contract.
- Shareable catalog state represented by URL search parameters.
- Responsive layouts that work from narrow mobile screens through desktop.
- Accessible navigation, forms, status messages, and keyboard interactions.
- Explicit loading, empty, not-found, degraded, and unexpected-error states.
- Reproducible host and Docker development workflows.
- Automated component, integration, browser, and accessibility checks.
- Honest product language that does not imply an active recommender.

## 2. Stage Objectives

Stage 2 will deliver:

1. A Node.js and Next.js application under `apps/web` using the App Router,
   strict TypeScript, React, and Tailwind CSS.
2. Pinned project metadata, a committed package lock, and reviewed development
   dependencies.
3. Environment-based browser API configuration with no embedded secrets.
4. OpenAPI-derived TypeScript contracts and a small project-owned API client.
5. A responsive application shell with navigation, page metadata, design
   tokens, reusable primitives, and accessible focus behavior.
6. A truthful landing page whose primary action is catalog browsing.
7. A catalog page with title search, one genre filter, one tag filter, one
   platform filter, deterministic sorting, and pagination.
8. URL-backed catalog state that supports reloads, browser history, and
   shareable links.
9. A game-detail route using the existing numeric game identifier contract.
10. Deliberate cover-image fallbacks for the current image-free synthetic
    catalog.
11. Loading, empty, filtered-empty, out-of-range, validation, not-found,
    network, database, and unexpected-error experiences.
12. Unit, component, API-client, and real-browser tests, including automated
    accessibility checks.
13. A web development container, full-stack Compose workflow, and documented
    direct PowerShell and npm equivalents.
14. Root and application documentation that describes only verified commands
    and behavior.

## 3. Non-Goals

The following work is intentionally excluded from Stage 2:

- Recommendation ranking, recommendation endpoints, or recommendation result
  pages.
- Preference onboarding or preference-submission APIs.
- Like, dislike, played, wishlist, rating, or other feedback writes.
- Authentication, authorization, accounts, or personalized persistence.
- Changes to the database schema, seed schema, or machine-learning boundary.
- A frontend-owned ranking, popularity formula, or fake recommendation
  fallback.
- A Next.js backend-for-frontend, proxy API, or direct PostgreSQL access.
- External metadata imports, cover-image downloads, or undocumented remote
  image hosts.
- LLM features, natural-language preference input, or generated explanations.
- Internationalization, a CMS, a PWA, native mobile applications, or offline
  synchronization.
- Product analytics, tracking pixels, advertising, or third-party session
  replay.
- GitHub Actions or broader CI/CD work; the verified command interface should
  remain automation-ready for Stage 7.
- Production deployment, production container hardening, CDN configuration,
  or monitoring; these remain Stage 7 concerns.
- Broad API refactoring. A genuine contract blocker must be documented and
  resolved explicitly rather than hidden in frontend workarounds.

## 4. Engineering Principles

### 4.1 Contract-First Integration

The verified live Stage 1 OpenAPI document is the external-contract source of
truth. Frontend types must be generated from it or mechanically checked
against it; handwritten copies of response models must not silently diverge.

### 4.2 Honest Product State

The interface must not show recommendation actions, fabricated scores, or
language that implies a trained model. Stage 2 may describe recommendations as
future work, but catalog browsing is the only active product capability.

### 4.3 URL as Catalog State

Search, taxonomy filters, sort, and page belong in the URL. Reload, browser
back/forward, bookmarks, and shared links must reproduce the same catalog
request without a global state store.

### 4.4 Explicit User States

Loading, unfiltered empty, filtered empty, out-of-range, validation,
not-found, backend unavailable, and unexpected failure are different states.
They require deliberate copy and recovery actions instead of one generic
fallback.

### 4.5 Accessibility by Construction

Semantic HTML, landmarks, heading order, labels, native controls, visible
focus, keyboard access, reduced-motion support, and status announcements are
part of each component's definition of done.

### 4.6 Responsive by Default

Every route is designed for narrow screens first and verified at representative
mobile, tablet, laptop, and wide-desktop viewports. No core action may depend
on hover or a desktop-only layout.

### 4.7 Small Client Boundary

The static landing page and shared shell remain server-renderable. Focused
catalog and detail client components own browser API access and interaction;
the entire application is not converted into one client boundary.

### 4.8 Minimal Dependency Surface

Native web controls and project-owned components are preferred when they meet
the requirement. Every runtime dependency must have a clear Stage 2 purpose
and pass compatibility and licensing review.

### 4.9 Deterministic Behavior

URL parsing, query serialization, pagination, number/date formatting, loading
transitions, and test fixtures must be predictable. Request races must not let
stale responses replace newer state.

### 4.10 Safe Configuration

Only explicitly public configuration may use the `NEXT_PUBLIC_` prefix. The
web application must not receive database credentials or other backend-only
environment values.

### 4.11 Incremental Delivery

Each implementation phase must leave the web project installable, testable,
and understandable. Page work begins only after the runtime, type boundary,
and shared state conventions are stable.

## 5. Proposed Technical Decisions

### 5.1 Runtime and Framework

- An active Node.js LTS release, selected and pinned after the Phase 0
  compatibility smoke test.
- npm with a committed `package-lock.json`.
- Next.js App Router.
- React and strict TypeScript.
- Tailwind CSS with project-owned CSS variables for design tokens.

Exact runtime and framework versions will be recorded only after install,
development-server, test-runner, and production-build smoke tests pass
together. A generator's floating defaults must not become the lock policy.

### 5.2 Rendering and Network Boundary

The landing page and shared shell remain server-rendered. Catalog and detail
data are fetched by focused client components because the current
configuration exposes a browser-visible API URL and Stage 1 explicitly allows
the web origin through CORS.

Stage 2 will not fetch FastAPI data from a Server Component. That avoids
requiring a second server-only URL when the web container cannot reach the host
API through browser-oriented `localhost`. Feature components own primary data
loading and failure states; route-level `loading.tsx` and `error.tsx` files
cover navigation, code loading, and framework-level failures.

The required dependency direction is:

```text
route -> feature component/hook -> typed API client -> FastAPI
```

The web application will call FastAPI over HTTP. It will not import backend
Python models, connect to PostgreSQL, or introduce a second API layer.

### 5.3 API Contract and Client

- `/openapi.json` is the input to generated TypeScript contract types.
- Generated output is committed so a clean frontend install does not require a
  running API.
- A documented refresh command updates generated types from a verified local
  API.
- A check command detects generated-contract drift.
- A small wrapper owns base-URL handling, query serialization, response
  JSON parsing, cancellation, and error normalization.
- Feature components consume domain-neutral client results rather than calling
  `fetch` independently.
- The client preserves the backend error code for programmatic handling while
  presenting safe, user-focused messages.
- No automatic retry loop is required. User-initiated retry is explicit.

Generated TypeScript contracts do not provide runtime validation. Stage 2 will
detect non-JSON responses and validate the small standard error-envelope shape.
Broader runtime response-schema validation is optional only if the Phase 0
dependency review justifies its cost; that decision must be recorded rather
than implied by static types.

### 5.4 Routes and URL Contract

Stage 2 owns these routes:

| Route | Purpose |
| --- | --- |
| `/` | Product introduction and catalog call to action |
| `/games` | Searchable, filterable, sortable, paginated catalog |
| `/games/[gameId]` | Game details using the Stage 1 numeric ID |

The catalog query contract mirrors the API:

- `q`
- `genre`
- `tag`
- `platform`
- `sort`
- `page`

The UI will request the API's default page size of 20 and will not expose a
page-size control in Stage 2. Only one value per taxonomy is allowed because
the backend does not implement multi-value filter semantics. Combined
taxonomy filters use the backend's AND semantics.

A project-owned runtime parser, not the generated TypeScript types, enforces:

- Trimmed `q` is either omitted or contains 1 through 200 characters.
- `page` is an integer from 1 through 1,000,000.
- Taxonomy slugs use lowercase alphanumeric segments separated by single
  hyphens.
- `sort` is one of `popularity`, `rating`, `release_date`, or `title`.
- `gameId` is an integer from 1 through 2,147,483,647.

A syntactically valid but unknown taxonomy slug is sent to the API and produces
a filtered-empty result. A malformed or out-of-bounds deep link produces a
recoverable invalid-link state without issuing a request. Any filter or sort
change resets `page` to 1.

### 5.5 State Ownership

- URL search parameters own catalog request state.
- Component state owns transient UI concerns such as an open mobile filter
  panel or an in-progress search input.
- Server data is fetched through the typed client and is not copied into a
  general-purpose global store.
- No Redux-style state library is planned for Stage 2.
- Browser history remains the source of truth for returning to a prior catalog
  query from a detail page.

### 5.6 Styling, Media, and Reusable UI

- CSS variables define color, spacing, radius, shadow, and typography tokens.
- Tailwind utilities consume those tokens instead of scattering unrelated
  literal values.
- The initial theme uses system fonts so local development does not depend on a
  font CDN.
- Native form elements are preferred for search and single-value filters.
- Current null cover URLs render a consistent project-owned placeholder.
- Remote images are not enabled until an explicit source and host allowlist are
  documented.
- Motion is limited, non-essential, and disabled when the user requests
  reduced motion.

### 5.7 Configuration

`NEXT_PUBLIC_API_URL` is the only required browser configuration in the
current plan. It must:

- Use `http://` or `https://`.
- Be an absolute base URL with a host and optional port or path prefix.
- Avoid embedded credentials, query strings, and fragments.
- Be normalized without a trailing slash before request paths are joined.
- Fail with a clear development/build error when invalid.

The ignored root `.env` remains the source for Docker Compose. Direct npm work
from `apps/web` will use an ignored `apps/web/.env.local` copied from a tracked
`apps/web/.env.example`; Next.js does not automatically load the repository
root `.env` from that project directory. Both examples must use the same safe
development default and must not contain secrets.

`NEXT_PUBLIC_` values are embedded into a production client bundle during
`next build`. Stage 2 must therefore supply and verify the API URL before each
production build. Its development container may inject the value when the
development server starts; changing a previously built production bundle at
container runtime is explicitly unsupported until Stage 7 defines a deployment
strategy.

If Stage 2 adds a configurable published web port, it will use a separate
documented variable such as `WEB_PORT`; it must not reuse API or database
settings.

### 5.8 Quality Tooling

The planned quality stack is:

- ESLint for code-quality rules.
- Prettier for deterministic formatting.
- `tsc --noEmit` for strict type checking.
- Vitest and React Testing Library for fast tests.
- Mock Service Worker or an equivalently scoped request mock for component
  integration tests.
- Playwright for browser workflows and representative viewports.
- axe-core integration for automated accessibility checks.

The full interaction suite should use Playwright's pinned Chromium browser.
Critical navigation and layout smoke paths should also run in its pinned
Firefox and WebKit browsers so the stage does not rely on one rendering
engine.

`npm ci` does not install Playwright browser binaries. The Docker-first E2E
workflow will therefore use an official Playwright test image pinned to the
same Playwright version as `package-lock.json`. An optional host workflow will
provide an explicit browser-install command before `npm run test:e2e`.

The final dependency choices and versions remain subject to the Phase 0
compatibility smoke test.

## 6. Target Repository Structure

```text
apps/web/
|-- src/
|   |-- app/
|   |   |-- games/
|   |   |   |-- [gameId]/
|   |   |   |   |-- error.tsx
|   |   |   |   |-- loading.tsx
|   |   |   |   `-- page.tsx
|   |   |   |-- error.tsx
|   |   |   |-- loading.tsx
|   |   |   `-- page.tsx
|   |   |-- error.tsx
|   |   |-- globals.css
|   |   |-- layout.tsx
|   |   |-- not-found.tsx
|   |   `-- page.tsx
|   |-- components/
|   |   |-- layout/
|   |   `-- ui/
|   |-- features/
|   |   |-- catalog/
|   |   `-- game-detail/
|   |-- lib/
|   |   |-- api/
|   |   |   |-- client.ts
|   |   |   |-- errors.ts
|   |   |   `-- generated.ts
|   |   |-- config.ts
|   |   |-- format.ts
|   |   `-- routes.ts
|   `-- test/
|       |-- fixtures/
|       |-- mocks/
|       `-- setup.ts
|-- e2e/
|   |-- accessibility.spec.ts
|   |-- catalog.spec.ts
|   `-- navigation.spec.ts
|-- public/
|   `-- images/
|-- scripts/
|   `-- api-types.mjs
|-- .dockerignore
|-- .env.example
|-- Dockerfile
|-- eslint.config.mjs
|-- next.config.ts
|-- package-lock.json
|-- package.json
|-- playwright.config.ts
|-- postcss.config.mjs
|-- prettier.config.mjs
|-- tsconfig.json
|-- vitest.config.ts
`-- README.md
```

The exact component filenames may evolve during implementation. The required
boundaries are routes, feature-level behavior, reusable UI, API access,
configuration, tests, and generated contracts.

Stage 2 will also add `infra/docker-compose.e2e.yml` for an isolated,
disposable-PostgreSQL browser-test stack. It must not reuse the persistent
development database volume.

## 7. Implementation Phase 0: Preflight and Baseline

### Objective

Confirm the Stage 1 handoff, current repository state, and compatible frontend
toolchain before generating or committing application files.

### Work

1. Confirm the working tree contains no unrelated or secret changes.
2. Re-run the development and integration Compose configuration checks.
3. Start PostgreSQL and the API, migrate, and seed using the documented Stage 1
   lifecycle.
4. Capture the current OpenAPI route inventory and representative catalog,
   detail, taxonomy, validation, not-found, and model-status responses.
5. Verify browser-origin CORS for `http://localhost:3000`.
6. Confirm pagination, filter, sort, null-field, and error-envelope behavior
   against the running API.
7. Test a small candidate matrix of Node.js LTS, Next.js, TypeScript,
   Tailwind, test-runner, and browser-test versions.
8. Select the smallest compatible dependency set and record relevant licenses.
9. Define the Stage 2 route inventory and user-state matrix.
10. Record a lightweight responsive design direction before building reusable
    components.
11. Confirm the target branch and intended commit boundaries.

### Verification

- `git status --short`
- `git diff --check`
- `docker compose --profile quality config --quiet`
- `docker compose -f infra/docker-compose.test.yml config --quiet`
- `GET /health` returns ready.
- `GET /openapi.json` includes every Stage 1 route consumed by the web app.
- Representative seeded catalog and detail responses match the documented
  schemas.
- An allowed-origin preflight succeeds and an unknown origin is not allowed.
- A temporary framework skeleton can install, type-check, test, and build with
  the selected version set.

### Exit Criteria

- The Stage 1 API contract is sufficient for every Stage 2 route.
- Runtime and tooling versions are chosen from evidence rather than floating
  defaults.
- The route, state, and responsive-surface inventory is written down.
- No backend or database change is required to begin frontend scaffolding.

## 8. Implementation Phase 1: Next.js and TypeScript Skeleton

### Objective

Create the smallest installable, testable, and buildable frontend project
without prematurely implementing product pages.

### Work

1. Create `apps/web/package.json` with exact direct dependencies, scripts, and
   a compatible Node engine declaration.
2. Commit the npm lock produced by a clean install.
3. Add strict TypeScript and import-alias configuration.
4. Add the minimal App Router root layout and placeholder home page.
5. Configure Tailwind and global CSS without importing network assets.
6. Configure ESLint and Prettier as separate, explicit checks.
7. Configure Vitest, DOM assertions, and shared test setup.
8. Add a minimal render test and a framework smoke test.
9. Add ignored paths for build, coverage, browser-test, and local environment
   artifacts.
10. Update the `apps/web` planning README and its current-command-status
    section only with skeleton commands that have passed.
11. Keep package lifecycle scripts free of hidden migrations, seeding, or
    network downloads beyond dependency installation.

### Verification

- `npm ci`
- `npm run dev`
- `npm run typecheck`
- `npm run lint`
- `npm run format:check`
- `npm run test`
- `npm run build`
- The root route renders with no browser-console exception.
- A clean reinstall produces no lockfile change.

### Exit Criteria

- The frontend installs reproducibly from its committed lock.
- Development and production compilation both succeed.
- Type, lint, format, and fast-test commands are independent and documented.
- No product behavior depends on unreviewed generator boilerplate.

## 9. Implementation Phase 2: Configuration and Typed API Boundary

### Objective

Establish one validated configuration source and one testable API access path
before any feature component fetches data.

### Work

1. Validate and normalize `NEXT_PUBLIC_API_URL` in a focused configuration
   module.
2. Add a tracked `apps/web/.env.example` and document the ignored
   `apps/web/.env.local` host workflow separately from root Compose
   configuration.
3. Add a documented OpenAPI type-generation command.
4. Generate and commit TypeScript contracts from the verified Stage 1
   `/openapi.json`.
5. Add a check mode that fails when committed generated contracts are stale.
6. Implement a typed request wrapper that joins paths safely and serializes
   only defined query values.
7. Normalize successful responses and the standard backend error envelope.
8. Represent network, abort, malformed-response, validation, not-found,
   unavailable, and unexpected failures as safe client error categories.
9. Preserve HTTP status and backend error code without exposing raw internal
   exception detail to users.
10. Cancel obsolete requests when URL state changes or a consuming component
    unmounts.
11. Add typed client methods for catalog pages, game details, and taxonomy.
12. Retain the generated model-status contract without adding a permanent
    `not_configured` assertion that would fail when Stage 3 activates a model.
13. Ensure tests can inject a base URL and mock transport without reading the
    developer's local `.env`.

### Verification

- A clean type-generation run produces deterministic output.
- Check mode detects a deliberately stale generated contract.
- Query parameters are URL-encoded and empty optional values are omitted.
- Success responses retain nullable dates, ratings, publishers, developers,
  and cover URLs correctly.
- The wrapper distinguishes HTTP 404, HTTP 422, HTTP 503, network failure,
  malformed JSON, and request cancellation.
- Error messages shown to a component contain no database URL, stack trace, or
  internal exception string.
- Rapid request replacement cannot render an older response over a newer one.
- Direct npm and Compose workflows resolve the same documented development API
  URL from their distinct environment-file locations.

### Exit Criteria

- Feature code has one typed, documented route to FastAPI.
- OpenAPI drift is detectable before release.
- Environment failures are early and understandable.
- API failure semantics are stable enough for page-specific recovery states.

## 10. Implementation Phase 3: Design Tokens, Shared UI, and App Shell

### Objective

Build the accessible visual and navigation foundation used by every Stage 2
route.

### Work

1. Define semantic color, spacing, type, radius, focus, and elevation tokens.
2. Establish mobile-first content widths, gutters, and responsive breakpoints.
3. Build the root layout with metadata, header, primary navigation, main
   landmark, and footer.
4. Add a visible-on-focus skip link.
5. Define consistent link, button, input, select, badge, card, skeleton,
   notice, empty-state, and pagination primitives.
6. Use native controls and explicit labels before considering custom widgets.
7. Add a reusable project-owned cover placeholder with stable aspect ratio.
8. Provide focus, hover, active, disabled, and error styles with sufficient
   contrast.
9. Respect `prefers-reduced-motion`.
10. Ensure long titles, long taxonomy names, and zoomed text do not break the
    layout.
11. Add focused component tests and accessibility checks for interactive
    primitives.

### Verification

- Header, main content, and footer use semantic landmarks.
- All interactive elements are reachable and operable by keyboard.
- Focus is always visible.
- Inputs and selects have programmatic names and associated help/error text.
- Automated accessibility checks report no serious or critical violations for
  the shell and component examples.
- Representative views at 320, 375, 768, 1024, and 1440 CSS pixels have no
  page-level horizontal overflow.
- Text remains usable at 200% browser zoom.

### Exit Criteria

- Feature pages can be assembled from consistent shared primitives.
- Navigation works without a pointer device.
- Responsive behavior is defined before page-specific layout work expands.
- The shell makes no claim that recommendations are currently available.

## 11. Implementation Phase 4: Landing Page

### Objective

Introduce GameLens AI truthfully and give users a clear path into the working
catalog.

### Work

1. Create a concise hero with a primary link to `/games`.
2. Explain the project-owned recommendation direction without describing a
   model as active.
3. Present the currently available catalog capability separately from planned
   recommendation features.
4. Add a small feature overview grounded in existing Stage 1 behavior.
5. Use project-owned decorative assets only when they add clear value.
6. Provide responsive layout and sensible reading order without animation
   dependencies.
7. Add route metadata and a unique page heading.
8. Test primary navigation, CTA behavior, truthful content, and responsive
   layout.

### Verification

- The primary CTA opens `/games`.
- The page has one clear top-level heading and logical heading order.
- No active-recommendation action or fabricated recommendation evidence is
  visible.
- Content remains complete when CSS motion is disabled.
- The page passes the shared keyboard, accessibility, console, and viewport
  smoke checks.

### Exit Criteria

- A first-time user can understand what works now and what is planned later.
- Catalog browsing is reachable through an obvious primary action.
- The landing page does not require API availability to render its core
  content.

## 12. Implementation Phase 5: Catalog Experience

### Objective

Expose the complete Stage 1 browse contract through a shareable, resilient,
and accessible catalog interface.

### Work

1. Parse and normalize catalog URL search parameters in one module.
2. Build a labeled title-search form that omits a blank `q` parameter and does
   not imply broader full-text search.
3. Load genre, tag, and platform options from their typed endpoints.
4. Present only single-value taxonomy controls.
5. Support `popularity`, `rating`, `release_date`, and `title` sorts using
   reader-friendly labels.
6. Reset the page to 1 when search, filter, or sort changes.
7. Provide a clear-all action that restores the canonical `/games` URL.
8. Fetch catalog and metadata independently so metadata failure does not erase
   successfully loaded games.
9. Cancel stale catalog requests during rapid URL changes.
10. Render game cards with title, key taxonomy, available rating/release
    context, and a deterministic cover placeholder.
11. Link every card to `/games/[gameId]`.
12. Render total-result context and accessible previous/next or numbered
    pagination.
13. Distinguish:
    unfiltered empty catalog, filtered no results, out-of-range page, catalog
    error, and metadata error.
14. Provide safe retry and reset actions where they can recover.
15. Preserve URL state across reload and browser back/forward navigation.
16. Announce meaningful result-count changes without repeatedly announcing
    decorative skeletons.

### Verification

- Direct links reproduce every supported search/filter/sort/page combination.
- Search values containing spaces and reserved URL characters are encoded
  correctly.
- Empty search input removes `q`.
- Malformed page, sort, slug, or overlong-search links issue no request and
  provide a reset path.
- Each taxonomy filter maps to exactly one API slug.
- Combined taxonomy controls preserve the API's AND semantics.
- Search length and page-boundary cases match the documented API limits.
- All sort labels map to documented API values.
- Changing any request-defining control resets page to 1.
- Browser back and forward restore both controls and results.
- An unknown taxonomy slug produces a filtered-empty state, not a crash.
- An out-of-range page offers a path back to available results.
- Null covers, ratings, dates, developers, and publishers render deliberate
  fallbacks.
- Metadata failure leaves an already successful catalog visible.
- A superseded request cannot overwrite the latest results.
- Pagination has an accessible name and correct disabled/current state.

### Exit Criteria

- Every Stage 1 catalog query capability is usable from the frontend.
- Catalog state is reloadable, bookmarkable, and shareable.
- Loading, empty, partial-failure, and full-failure states are recoverable.
- The page remains usable at all representative viewports and with a keyboard.

## 13. Implementation Phase 6: Game Detail Experience

### Objective

Present one game's reader-relevant Stage 1 metadata with reliable deep-link,
loading, not-found, and failure behavior.

### Work

1. Add the `/games/[gameId]` route using the existing positive-integer API
   identifier.
2. Reject malformed or out-of-range route values before issuing a request.
3. Fetch details through the typed API client.
4. Render title, description, release date, developer, publisher, rating,
   rating count, genres, tags, and platforms when available.
5. Keep the contract ID and slug available for routing and application logic,
   but do not present them as primary reader content. Do not present synthetic
   `popularity_score` or audit timestamps as recommendation evidence.
6. Use stable locale-independent formatting rules in tests and intentional
   reader-facing formatting in the browser.
7. Reuse the project-owned cover placeholder for null image data.
8. Add a clear route back to the catalog; normal browser history must also
   preserve the prior query.
9. Map `game_not_found` and invalid identifiers to a not-found experience.
10. Keep network, unavailable-backend, malformed-response, and unexpected
   failures recoverable without pretending the game does not exist.
11. Add a route-specific loading skeleton with stable layout.
12. Do not add recommendation, preference, or feedback controls.
13. Add unique route metadata using only data available safely at render time.

### Verification

- A known seeded ID renders all reader-relevant fields and taxonomy.
- Nullable values never render as `null`, `undefined`, `NaN`, or an invalid
  date.
- A missing game renders the not-found experience.
- An ID below 1, above 2,147,483,647, or not composed as an integer does not
  issue a game-detail API request.
- Backend-unavailable and unexpected errors show safe retry guidance.
- Browser back returns to the previous catalog URL state.
- The detail route passes keyboard, accessibility, console, and representative
  viewport checks.

### Exit Criteria

- Seeded game details are directly linkable and readable.
- Not-found behavior is distinct from operational failure.
- No control implies a backend capability that Stage 2 does not have.
- Detail rendering is resilient to every nullable Stage 1 field.

## 14. Implementation Phase 7: Cross-Cutting Resilience and Accessibility

### Objective

Audit the complete application as one product rather than relying only on
isolated component correctness.

### Work

1. Add root error and not-found boundaries with useful recovery paths.
2. Confirm route-level loading boundaries do not cause layout collapse.
3. Move focus or announce route/result changes where client navigation would
   otherwise be ambiguous.
4. Ensure status messages use appropriate live regions without excessive
   announcements.
5. Verify validation messages identify the affected control and correction.
6. Test color contrast, zoom, keyboard order, skip navigation, and visible
   focus across all routes.
7. Test narrow layouts with long fixture content and no cover images.
8. Confirm the application remains understandable with reduced motion and with
   decorative images unavailable.
9. Remove browser-console errors, hydration warnings, duplicate keys, and
   unhandled promise rejections.
10. Review client-side JavaScript and dependency additions for unnecessary
    weight.
11. Confirm no public response, rendered page, source map, or client bundle
    contains backend credentials.

### Verification

- Automated accessibility checks report no serious or critical violations on
  `/`, `/games`, a populated detail route, and all testable error states.
- A keyboard-only smoke path can reach the catalog, change controls, paginate,
  open a game, and return.
- Page-level horizontal overflow is absent at all representative viewports.
- Browser logs contain no application error during happy-path navigation.
- Backend downtime produces a controlled page state rather than an unhandled
  rejection.
- A search of built client output finds no database URL or credential value.

### Exit Criteria

- Accessibility and resilience are verified across complete workflows.
- All route boundaries recover or redirect intentionally.
- The client bundle contains only explicitly public configuration.
- Remaining limitations are documented rather than concealed.

## 15. Implementation Phase 8: Docker and Development Commands

### Objective

Provide a reproducible full-stack workflow while preserving the direct host
workflow and all safe Stage 1 lifecycle operations.

### Work

1. Use `apps/web` as the web-image build context and create its `Dockerfile`
   from the selected, pinned Node.js runtime.
2. Install dependencies with `npm ci` and run as a non-root user where
   practical.
3. Add `.dockerignore` at the `apps/web` build-context root and verify that
   `node_modules`, `.next`, coverage, and browser artifacts are excluded.
4. Add a development-oriented `web` service to `docker-compose.yml`.
5. Publish the web service on loopback only, defaulting to port 3000.
6. Inject only browser-public configuration before the development server
   starts; supply public build values before any production-build check.
7. Make full-stack startup respect API readiness without moving migrations or
   seeding into ordinary web startup.
8. Add a web health check that proves the HTTP server is responding.
9. Decide and document a Windows-compatible source-mount and `node_modules`
   strategy for development.
10. Add `infra/docker-compose.e2e.yml` with a fresh disposable or `tmpfs`
    PostgreSQL database, migrated and seeded API, web service, and an official
    Playwright test image that exactly matches the locked Playwright package.
11. Use internal Compose origins such as `http://web:3000` and
    `http://api:8000` only inside the E2E network, with a matching explicit
    CORS origin. Keep host-browser development on the loopback URLs.
12. Add a documented optional host command that installs the locked
    Chromium, Firefox, and WebKit browser binaries before browser tests.
13. Preserve existing API-specific commands and add web-specific root commands
    only after their direct npm and Compose equivalents work.
14. Update root startup commands to make the complete db/API/web path clear.
15. Keep production image optimization and deployment configuration deferred
    to Stage 7.

### Verification

- `docker compose --profile quality config --quiet`
- `docker compose -f infra/docker-compose.e2e.yml config --quiet`
- `docker compose build web`
- `npm run playwright:install` for the optional host-browser workflow.
- `docker compose -f infra/docker-compose.e2e.yml run --rm e2e` for the
  Docker-first browser workflow.
- Explicit Stage 1 migrate and seed commands.
- `docker compose up -d db api web`
- `docker compose ps`
- `GET http://localhost:3000/` returns the landing page.
- Browser catalog requests reach `http://localhost:8000` through the configured
  CORS origin.
- Source edits are reflected according to the documented development mode.
- The isolated E2E project starts from an empty database, migrates, seeds
  exactly 30 games, and runs browser tests without a browser download during
  the routine container workflow.
- Removing the E2E project cannot remove or mutate the persistent development
  volume.
- `docker compose down` stops services without deleting the PostgreSQL volume.

### Exit Criteria

- Both host-npm and Docker-first frontend workflows are documented and work.
- The complete development stack becomes healthy.
- Web startup does not mutate schema or catalog data.
- Existing Stage 1 API, test, and database commands remain available.
- No secret is embedded in the image or browser bundle.

## 16. Implementation Phase 9: Test Matrix and Quality Gate

### Objective

Validate types, components, browser behavior, API integration, accessibility,
container startup, and documentation before Stage 2 is considered complete.

### Fast Test Suite

- Configuration validation and URL joining.
- Catalog query parsing, normalization, and serialization.
- Date, rating, count, and nullable-value formatting.
- Project-owned API-client success and failure handling using OpenAPI-derived
  contracts.
- Request cancellation and stale-response protection.
- Shared control and state components.
- Landing-page truthfulness and navigation.
- Catalog populated, empty, filtered-empty, partial-error, and full-error
  states.
- Detail populated, not-found, invalid-ID, and unavailable states.

### Browser Test Suite

- Landing page to catalog navigation.
- Search, each taxonomy filter, each sort, clear-all, and pagination.
- URL reload plus browser back/forward restoration.
- Catalog card to detail navigation and return.
- Known and unknown game detail routes.
- API-unavailable and retry behavior using controlled interception.
- Keyboard-only critical path.
- Automated accessibility scans.
- Representative mobile, tablet, and desktop viewport smoke paths.
- Full interaction coverage in pinned Chromium plus critical route and layout
  smoke paths in pinned Firefox and WebKit.

### Real API Integration Suite

- Start the separate E2E Compose project with disposable PostgreSQL, the
  verified Stage 1 API, the Stage 2 web service, and the pinned browser-test
  image.
- Apply migrations and seed explicitly inside that isolated project.
- Generate or check frontend contracts against the live OpenAPI document.
- Run read-only browser workflows against the 30-game deterministic catalog.
- Confirm the frontend sends only documented query parameters.
- Confirm no Stage 2 UI exposes a recommendation action. Record the current
  model status as baseline evidence without a permanent `not_configured`
  assertion that would make Stage 3 fail.
- Tear down the isolated project and prove that it never mounted, reset, or
  deleted the persistent development volume.

### Stage 1 Regression Suite

- Run the fast API unit and contract suite through the current-source quality
  service.
- Run Ruff lint and format checks for API application code, tests, and
  migrations.
- Run the existing disposable-PostgreSQL integration suite through its
  explicit reset-safety guard.
- Re-run the Stage 1 health, catalog, detail, taxonomy, model-status, OpenAPI,
  and documentation HTTP smoke matrix.
- Record the results without replacing Stage 1's historical completion
  evidence.

The regression command set must include the direct equivalents of:

```powershell
docker compose run --build --rm --no-deps quality python -m pytest tests/unit -q -p no:cacheprovider
docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic
docker compose run --build --rm --no-deps quality python -m ruff format --no-cache --check app tests alembic
docker compose -f infra/docker-compose.test.yml up -d test-db
try {
    docker compose -f infra/docker-compose.test.yml run --build --rm test-api
} finally {
    docker compose -f infra/docker-compose.test.yml down --remove-orphans
}
```

### Static Checks

- Strict TypeScript check.
- ESLint.
- Prettier check.
- Unit/component tests.
- Production Next.js build.
- OpenAPI generated-contract drift check.
- Stage 1 fast, PostgreSQL integration, Ruff, and HTTP regression checks.
- Dependency and license review.
- `git diff --check`.
- Development and test Compose validation.
- Secret, generated-artifact, and ignored-file review.

### Coverage Policy

- Generate a coverage report for project-owned TypeScript and React code.
- Exclude generated API types, framework configuration, and static assets from
  coverage targets.
- Treat coverage as diagnostic during Stage 2; do not substitute a percentage
  for explicit route and failure-path tests.
- Record meaningful untested branches in the completion evidence.

### Operational Smoke Test

1. Build the API and web images.
2. Start PostgreSQL.
3. Apply Alembic migrations and seed explicitly.
4. Start the API and web services.
5. Confirm all three services are healthy.
6. Open the landing page, catalog, a filtered catalog URL, and a known detail
   route.
7. Exercise loading, filtered-empty, not-found, and API-unavailable states.
8. Inspect browser console and representative viewport layouts.
9. Stop the stack with `docker compose down`.
10. Confirm the named PostgreSQL volume remains present.

### Exit Criteria

- All type, lint, format, unit, component, browser, and build checks pass.
- Real-API browser workflows pass against a fresh deterministic E2E database.
- Stage 1 regression checks pass.
- Automated accessibility checks pass under the documented severity policy.
- The full Docker development stack becomes healthy.
- OpenAPI generated contracts are current.
- Operational and visual smoke tests pass.
- Remaining limitations and evidence are recorded.

## 17. Implementation Phase 10: Documentation and Release Preparation

### Objective

Make the completed frontend reproducible, reviewable, and ready to support the
content-recommendation stage.

### Work

1. Update the root README with verified frontend setup, startup, test, build,
   and route instructions.
2. Replace the current-command-status section in `apps/web/README.md` with
   verified direct npm, PowerShell, and Docker workflows.
3. Update `docs/architecture.md` to describe implemented render, state, and API
   boundaries.
4. Change the Stage 2 status in `docs/roadmap.md` to Complete only after the
   acceptance gate passes.
5. Update infrastructure documentation to include the verified web service and
   health behavior.
6. Record exact runtime/tool versions and implementation-time decisions.
7. Record commands actually executed and their outcomes in Section 23.
8. Document current limitations:
   no active recommender, onboarding, feedback, authentication, imported
   covers, or production deployment.
9. Review every README command against a clean install or Docker workflow.
10. Review the complete diff for secrets, generated build output, browser-test
    artifacts, dead placeholders, and unrelated changes.

### Suggested Commit Structure

1. `chore(web): scaffold Next.js app and quality tooling`
2. `feat(web): add typed API client and shared application shell`
3. `feat(catalog): add browse and game detail experiences`
4. `test(web): add browser accessibility and full-stack checks`
5. `docs(web): record Stage 2 verification and handoff`

### Exit Criteria

- Setup is reproducible from a clean checkout.
- Every documented command exists and has been verified.
- Architecture and roadmap describe implemented rather than intended behavior.
- The final diff contains only Stage 2 scope.
- No local environment file, credential, build directory, coverage report,
  trace, video, or generated screenshot is tracked accidentally.
- The branch is ready for review and merge.

## 18. Command Interface Target

The following direct frontend scripts should exist only after their
implementations are verified:

- `npm run dev`
- `npm run build`
- `npm run start`
- `npm run typecheck`
- `npm run lint`
- `npm run format`
- `npm run format:check`
- `npm run test`
- `npm run test:coverage`
- `npm run playwright:install`
- `npm run test:e2e`
- `npm run api:types`
- `npm run api:types:check`

The following root command targets may be added after the corresponding direct
commands work:

- `make build-web`
- `make web`
- `make test-web`
- `make test-web-e2e`
- `make lint-web`
- `make format-web`
- `make api-types`

Existing Stage 1 commands must retain a clear direct equivalent. `make up` may
be extended to start the complete development stack only when the README and
help output are updated at the same time. GNU Make remains optional on Windows.

## 19. Acceptance Criteria

Stage 2 is complete only when all of the following are true:

- The frontend installs reproducibly with `npm ci`.
- Strict TypeScript, ESLint, Prettier, unit/component tests, and the production
  build pass.
- The selected Node.js, Next.js, React, TypeScript, Tailwind, test, and browser
  dependency versions are pinned and documented.
- Generated TypeScript contracts match the verified Stage 1 OpenAPI document.
- `NEXT_PUBLIC_API_URL` is validated for the app-local host workflow, Docker
  development startup, and production build; no backend secret enters the
  browser bundle.
- The landing page truthfully distinguishes working catalog functionality from
  planned recommendations.
- The catalog supports documented search, single-value taxonomy filters,
  sorting, and pagination.
- Catalog query state survives reload and browser back/forward navigation.
- A known game detail route renders every reader-relevant field safely.
- Loading, empty, filtered-empty, out-of-range, validation, not-found, network,
  database, and unexpected-error states behave as documented.
- Null image and metadata fields have intentional presentation fallbacks.
- All critical workflows are keyboard accessible with visible focus.
- Automated accessibility checks pass under the documented severity policy.
- Critical browser smoke paths pass in the pinned Chromium, Firefox, and
  WebKit engines.
- The Docker-first browser runner image matches the locked Playwright package,
  and the optional host browser-install command is documented.
- Representative mobile, tablet, laptop, and wide-desktop layouts have no
  page-level horizontal overflow.
- Real-browser workflows pass against a fresh isolated database containing the
  deterministic 30-game Stage 1 catalog.
- PostgreSQL, API, and web services become healthy through the Docker-first
  workflow.
- Web startup does not migrate, seed, reset, or delete development data.
- Existing Stage 1 API behavior and quality gates remain reliable.
- Root and application README commands match verified behavior.
- No secrets, local environment files, build output, test traces, or generated
  reports are committed.
- Known limitations and the Stage 3 handoff are documented.

## 20. Risks and Mitigations

**Risk:** Fast-moving frontend packages produce an incompatible toolchain.

**Mitigation:** Smoke-test the complete install, development, test, and build
matrix before pinning exact versions and building feature code.

**Risk:** Handwritten frontend models drift from FastAPI responses.

**Mitigation:** Generate TypeScript contracts from OpenAPI, commit deterministic
output, and make drift checking part of the acceptance gate.

**Risk:** A public environment variable is treated like a secret or is embedded
with the wrong build-time value.

**Mitigation:** Limit browser configuration to a validated public API URL,
document build/runtime behavior, and inspect built output for backend-only
values.

**Risk:** Browser requests fail because the web origin and CORS configuration
diverge.

**Mitigation:** Keep an explicit matching origin in `CORS_ORIGINS` and test both
allowed and rejected preflight behavior.

**Risk:** URL and component state enter synchronization loops or break browser
history.

**Mitigation:** Make normalized URL parameters the single request-state source,
centralize parsing/serialization, and test reload plus back/forward behavior.

**Risk:** Slow earlier requests overwrite current catalog results.

**Mitigation:** Abort superseded requests and test out-of-order completion.

**Risk:** Custom controls introduce keyboard and screen-reader defects.

**Mitigation:** Prefer native form controls, define accessibility in component
acceptance criteria, and run keyboard plus automated audits.

**Risk:** Missing covers or nullable metadata create broken cards and layout
shift.

**Mitigation:** Use a fixed-ratio project-owned placeholder and explicit text
fallbacks for every nullable API field.

**Risk:** The interface implies that recommendations already work.

**Mitigation:** Use catalog-first calls to action, test product copy, and expose
no recommendation controls while model status remains `not_configured`.

**Risk:** Metadata endpoint failure makes the entire catalog unusable.

**Mitigation:** Load metadata independently, retain successful game results,
and provide focused recovery for unavailable filters.

**Risk:** Browser tests become flaky or modify persistent development data.

**Mitigation:** Keep Stage 2 browser flows read-only, use a disposable E2E
database with deterministic seed data, wait on observable UI state, and never
mount or reset the persistent volume.

**Risk:** Playwright browser binaries are missing or do not match the package.

**Mitigation:** Pin the official test image to the locked Playwright version
and provide a separate explicit browser-install command for optional host runs.

**Risk:** The intended web `.dockerignore` is ignored because Docker uses a
different build context.

**Mitigation:** Use `apps/web` as the explicit web build context and keep its
`.dockerignore` at that context root.

**Risk:** Windows bind mounts or file watching behave differently from Linux.

**Mitigation:** Verify direct PowerShell and Docker workflows on the target
environment and document the chosen source-mount and dependency-volume policy.

**Risk:** Dependency growth increases bundle size and maintenance burden.

**Mitigation:** Require a specific use case for each runtime dependency and
review the client build before the final gate.

## 21. Implementation-Time Decisions

No implementation-time decisions are recorded yet because Stage 2 application
work has not started. This section must be updated as evidence resolves:

1. Exact Node.js, npm, Next.js, React, TypeScript, and Tailwind versions.
2. Exact OpenAPI generation and typed-request tooling.
3. Final Vitest, request-mocking, Playwright, and accessibility packages.
4. Exact Playwright test image and optional host browser-install behavior.
5. Confirmed app-local, Docker-development, and production-build environment
   handling.
6. Confirmed component boundaries within the browser-data-fetch design.
7. Confirmed catalog query normalization and request-cancellation behavior.
8. Confirmed Docker source-mount, file-watching, and `node_modules` strategy.
9. Confirmed web health check, E2E topology, and root command names.
10. Any API contract blocker and its explicitly approved resolution.
11. Runtime response-validation depth, if any, beyond JSON and error-envelope
   checks.
12. Diagnostic coverage and browser/a11y audit findings.

Every resolved decision must be reflected in implementation, tests, and
documentation.

## 22. Stage 3 Handoff

When complete, Stage 2 should leave the content-recommendation stage with:

- A stable responsive application shell and navigation model.
- Reusable accessible controls, cards, notices, loading states, and error
  boundaries.
- A generated and drift-checked TypeScript API contract.
- One project-owned API client that can be extended with recommendation
  endpoints.
- URL and request-state conventions that do not require a global store.
- Game-card and taxonomy presentation primitives that Stage 3 can extend for
  onboarding.
- Deterministic browser fixtures and full-stack test orchestration.
- An honest capability boundary that still reports no active recommendation
  model until Stage 3 provides one.

Stage 3 may add onboarding and recommendation experiences only after real
backend contracts and a validated model exist. It must not move ranking logic
into the browser.

## 23. Verified Completion Record

Pending implementation.

This section must remain unpopulated until every Stage 2 acceptance criterion
passes. The final record must include:

- Completion date and branch.
- Pinned runtime and major tooling versions.
- Type, lint, format, unit/component, browser, and build results.
- Diagnostic coverage result and meaningful gaps.
- OpenAPI generation and drift-check result.
- Accessibility and representative viewport audit result.
- Dependency and secret-review result.
- Full-stack container health and browser smoke result.
- Confirmation that the Stage 1 persistent database volume was not reset or
  deleted.
