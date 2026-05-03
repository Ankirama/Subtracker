# Frontend Component Testing Infrastructure — Design Spec

**Date:** 2026-05-03
**Status:** Approved (3 sections)
**Goal:** Stand up a minimal but production-grade React component testing setup, prove it with one real component test (`CancellationSuggestionBanner`), and unblock the CI test step that has been commented out since the test scaffolding was deferred.

---

## Context

The frontend has `vitest` and `@testing-library/*` listed in `frontend/package.json` devDependencies, but no test environment is configured:

- `vite.config.ts` has no `test:` block — Vitest defaults to a Node environment, which breaks anything touching `window`/`document`.
- `jsdom` is not installed.
- There is no setup file (`@testing-library/jest-dom` matchers are not registered).
- There is no test render helper, so each test would have to repeat the Chakra + QueryClient + Router + Auth + i18next provider stack.
- There is no HTTP mocking layer.
- `.github/workflows/ci.yml:150-153` has the frontend test step commented out:
  > `# Tests temporarily disabled - will be fixed in separate PR`
- Zero `*.test.tsx` files exist under `frontend/src/`.

The recently shipped cancellation-detection feature added `CancellationSuggestionBanner.tsx`, a banner that calls `acceptCancellation` / `dismissCancellation` mutations and triggers `onUpdate` callbacks. It is a good candidate to anchor the first test because:

- It calls the API directly via `subscriptionsAPI.acceptCancellationSuggestion` / `.dismissCancellationSuggestion` and exercises both success and error paths.
- It depends on Chakra UI (toast, button), so it validates the provider stack works.
- It conditionally renders based on `subscription.suggested_cancellation_status` AND `subscription.cancellation_suggestion_reason` being truthy (plus a local `isVisible` flag) — that gives us a clean visibility invariant to assert.

## Scope

**In scope (this spec):**

1. Wire up Vitest with jsdom + MSW + a shared render helper.
2. Add MSW base handlers for the endpoints any rendered component might hit incidentally (`/auth/me`, `/notifications/unread-count`).
3. Write a real test file for `CancellationSuggestionBanner` exercising the 5 scenarios listed in Section 3.
4. Re-enable the test step in CI.

**Out of scope:**

- Pixel-perfect rendering (snapshot/visual regression).
- Change-detector tests on Chakra icons or toast strings.
- Tests for any other component (those land in follow-up PRs).
- E2E / Playwright (covered separately by `docs/operations/` materials, not by this PR).
- Pre-commit hook integration (too slow — keep it CI-only for now).

## Section 1 — Wiring (Approved)

### New devDependencies

Add to `frontend/package.json`:

- `jsdom@^24` — DOM implementation Vitest will use as `environment`.
- `msw@^2` — HTTP-level mocking, intercepts `fetch`/`XMLHttpRequest` so Axios calls go through real client code.

`@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, and `vitest` are already present.

### Vitest config

Extend `frontend/vite.config.ts` with a `test:` block. Because the file is consumed by both Vite and Vitest, add a triple-slash reference for Vitest types:

```ts
/// <reference types="vitest" />
import { defineConfig } from 'vite'
// ... existing imports

export default defineConfig({
  // ... existing config (build, plugins, resolve, server)
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Exclude Playwright/e2e dirs and node_modules by default
  },
})
```

`globals: true` lets us use `describe`/`it`/`expect`/`vi` without imports — matches the team's existing Vitest familiarity.

### Setup file

Create `frontend/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
import '@/i18n/config' // initialize i18next as a side effect — same pattern as main.tsx
import { afterAll, afterEach, beforeAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import { server } from './server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  localStorage.clear() // AuthProvider reads `access_token` from localStorage on mount
})
afterAll(() => server.close())
```

`onUnhandledRequest: 'error'` is deliberate — any unmocked API call should fail loudly so we never accidentally hit real network in CI.

`@/i18n/config` import is required because the app's i18next instance is initialized as a side effect of being imported from `main.tsx`; tests don't load `main.tsx`, so we replicate that side effect here. Without it, any component using `useTranslation` (including `AuthProvider`) crashes.

### File naming convention

- **Component tests:** colocated `*.test.tsx` next to the component (e.g. `CancellationSuggestionBanner.test.tsx` next to `CancellationSuggestionBanner.tsx`).
- **Pure utility/hook tests:** colocated `*.test.ts` next to the source.

Rationale: colocation keeps the test discoverable when reading the component and aligns with how the backend has `tests/` per module — frontend just inlines them.

## Section 2 — Render Helper + MSW Handlers (Approved)

### `renderWithProviders`

Create `frontend/src/test/renderWithProviders.tsx`:

```tsx
import { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { ChakraProvider } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
// i18next provider import (existing initialization), if global init is sufficient,
// no provider wrapper is needed — confirm during implementation.

export interface ProviderOptions {
  route?: string
  queryClient?: QueryClient
  withAuth?: boolean
}

export function renderWithProviders(
  ui: ReactElement,
  options: ProviderOptions & Omit<RenderOptions, 'wrapper'> = {},
) {
  const {
    route = '/',
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { staleTime: Infinity, retry: false },
        mutations: { retry: false },
      },
    }),
    withAuth = true,
    ...renderOptions
  } = options

  // AuthProvider must be inside MemoryRouter — it calls useNavigate().
  const Wrapper = ({ children }: { children: React.ReactNode }) => {
    const inner = withAuth ? <AuthProvider>{children}</AuthProvider> : children
    return (
      <ChakraProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]}>{inner}</MemoryRouter>
        </QueryClientProvider>
      </ChakraProvider>
    )
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions })
}
```

Key choices:

- **Fresh `QueryClient` per call** — prevents cache leakage across tests; `staleTime: Infinity` + `retry: false` keeps tests deterministic.
- **`MemoryRouter`** instead of `BrowserRouter` — no real `window.location` mutation, easy to seed initial route via `route` option.
- **`withAuth = true` by default** — most components in this app sit behind auth; opting out is rarer than opting in. The real `AuthProvider` is used (not a mock) so tests exercise the actual auth context wiring. Note: `AuthProvider` only calls `getCurrentUser()` when `localStorage.access_token` is present — for "logged-in" tests, set the token before render (see helper extension below); otherwise the provider stays in unauthenticated mode and `/auth/me` is never hit. Either way, MSW has a default `/auth/me` handler so accidental calls don't error.
- **No `ColorModeScript`** — color mode is irrelevant for behavior tests and would add SSR-shaped noise.
- **i18n** — handled at the setup-file level by importing `@/i18n/config` (side-effect init). No `I18nextProvider` wrapper is needed because the global instance is what `useTranslation` reads.

Optional convenience: a small `loginAs(user?: Partial<User>)` helper that sets `localStorage.access_token` and primes the `/auth/me` MSW handler. Not required for the banner test (it doesn't need an authenticated user) but worth noting as the obvious extension point for the next test that does.

### MSW server

Create `frontend/src/test/server.ts`:

```ts
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

### Base handlers

Create `frontend/src/test/handlers.ts` with the minimum set of endpoints that incidental renders may hit. These can be overridden per test via `server.use(...)`.

```ts
import { http, HttpResponse } from 'msw'

export const defaultUser = {
  id: 'test-user-id',
  email: 'test@example.com',
  is_admin: false,
  display_name: null,
  preferred_language: 'en',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

export const handlers = [
  http.get('*/auth/me', () => HttpResponse.json(defaultUser)),
  http.get('*/notifications/unread-count', () => HttpResponse.json({ count: 0 })),
]
```

The `defaultUser` fields match the `User` interface in `frontend/src/types/index.ts` so consumers of `useAuth().user` get a fully-shaped object.

The `*` prefix matches whatever base URL the Axios client is configured with (relative or absolute). Per-test overrides look like:

```ts
server.use(
  http.post('*/subscriptions/:id/cancellation/accept', () =>
    HttpResponse.json({ ok: true }),
  ),
)
```

## Section 3 — First Test + CI Integration (Approved)

### `CancellationSuggestionBanner.test.tsx`

File: `frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx`.

Five scenarios. Component reference: `frontend/src/components/subscriptions/CancellationSuggestionBanner.tsx` — accept button label is **"Accept & Mark as Cancelled"**, dismiss button label is **"Dismiss Suggestion"**, and the banner title is **"AI Detected Potential Cancellation"**.

1. **Visibility invariant — does not render when no suggestion exists.**
   - Given a subscription with `suggested_cancellation_status = null` (or `cancellation_suggestion_reason = null`), the component returns `null`. Assert via `queryByText('AI Detected Potential Cancellation')` returning `null`.

2. **Rendering — banner renders when both suggestion fields are present.**
   - Given a subscription with both `suggested_cancellation_status` and `cancellation_suggestion_reason` set, assert the title, the suggestion reason text, and both action buttons are in the DOM.

3. **Accept calls API and triggers `onUpdate`.**
   - User clicks the button labelled "Accept & Mark as Cancelled".
   - MSW intercepts `POST */subscriptions/:id/cancellation/accept` and returns 200.
   - Assert the success toast title "Suggestion Accepted" appears (use `findByText` to await async settle), and the `onUpdate` mock is called exactly once.

4. **Dismiss calls API, hides the banner, and triggers `onUpdate`.**
   - User clicks the button labelled "Dismiss Suggestion".
   - MSW intercepts `POST */subscriptions/:id/cancellation/dismiss` and returns 200.
   - Assert: success toast title "Suggestion Dismissed" appears, the banner title disappears from the DOM (component sets `isVisible=false`), AND `onUpdate` mock is called exactly once.
   - Note: the component also has a `CloseButton` that calls the same dismiss handler. The test deliberately targets the labelled button, not the close button, to keep the test resilient to layout changes.

5. **Error toast on accept failure, and `onUpdate` is NOT called.**
   - MSW returns a 500 for the accept endpoint.
   - User clicks "Accept & Mark as Cancelled".
   - Assert: error toast with title "Error" and description "Failed to accept cancellation suggestion." appears in the DOM (`findByText`), AND the `onUpdate` mock is **not** called.

Each test uses `renderWithProviders(<CancellationSuggestionBanner subscription={fixture} onUpdate={vi.fn()} />)` and `userEvent.setup()` for interactions. A small fixture factory (`buildSubscriptionWithSuggestion(overrides?)`) lives at the top of the test file to keep each scenario terse.

### CI integration

Edit `.github/workflows/ci.yml`:

```yaml
      - name: Type checking with TypeScript
        working-directory: frontend
        run: npx tsc --noEmit --strict

      - name: Run unit tests
        working-directory: frontend
        run: npm test -- --run

      - name: Build check
        working-directory: frontend
        run: npm run build
```

Replace the commented-out block at lines 150-153. The `--run` flag forces single-run mode (Vitest defaults to watch).

**Not added to pre-commit:** the pre-commit hook (`scripts/pre-commit.sh`) already covers lint + tsc and we want it to stay fast. Tests run in CI only for now; we can promote to pre-commit later if the suite stays small.

## Implementation order

1. Add `jsdom` + `msw` to devDependencies, `npm install`.
2. Create `src/test/setup.ts`, `src/test/server.ts`, `src/test/handlers.ts`, `src/test/renderWithProviders.tsx`.
3. Add the `test:` block to `vite.config.ts`.
4. Write `CancellationSuggestionBanner.test.tsx`, run locally, watch all 5 scenarios pass.
5. Enable the CI test step in `.github/workflows/ci.yml`.
6. Verify CI passes.

## Risks & mitigations

- **`AuthProvider` only fetches `/auth/me` when `localStorage.access_token` exists.** Without a token it stays in unauthenticated mode and never hits the API. Tests that need an authenticated user must seed the token in `beforeEach` (or use the `loginAs` helper noted in Section 2). The banner test does not need this.
- **MSW v2 + Node 18+ requirement.** CI uses `actions/setup-node` — confirm the cached version is ≥ 18.17 during implementation; bump if needed.
- **Chakra `useToast` rendering in jsdom.** Toasts render into a portal at the document body. Use `findByText` (not `getByText`) so the assertion awaits the toast appearing, and query against `screen` (which scans the whole document) rather than the container returned by `render`.
- **Test runtime in CI.** Five tests should run in well under 5 seconds. If/when the suite grows, revisit sharding or `--threads`.

## Success criteria

- `npm test -- --run` from `frontend/` passes locally with 5 green tests.
- `tsc --noEmit --strict` continues to pass with the new test files.
- CI's "Frontend Quality & Security" job runs the test step and is green on the PR.
- Future component tests can be written by importing `renderWithProviders` and adding per-test `server.use(...)` handlers — no further infrastructure changes needed.
