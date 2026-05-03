# Frontend Component Testing Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up Vitest+jsdom+MSW frontend testing infrastructure with a shared `renderWithProviders` helper, prove it with five passing tests for `CancellationSuggestionBanner`, and re-enable the commented-out CI test step.

**Architecture:** Add jsdom + MSW v2 as devDependencies. Create a `frontend/src/test/` folder containing the bootstrap file, MSW server, base handlers, and provider helper. Configure Vitest via a `test:` block in `vite.config.ts`. Write the banner test as five scenarios sharing one fixture factory. Uncomment the CI step.

**Tech Stack:** React 18 + TypeScript, Vite 5, Vitest 1.2.1 (already in devDeps), `@testing-library/{react,jest-dom,user-event}` (already in devDeps), jsdom 24 (new), msw 2 (new). Node 20 in CI.

**Spec:** `docs/superpowers/specs/2026-05-03-frontend-component-testing-design.md`

**Branch:** Implementation should land on its own feature branch (e.g. `feat/frontend-component-testing`) cut from `main`. The current branch (`docs/frontend-component-testing-spec`) only carries the spec.

---

## File Map (locks decomposition)

**Created:**
- `frontend/src/test/setup.ts` — Vitest global setup: jest-dom matchers, MSW lifecycle, i18n side-effect import, localStorage cleanup.
- `frontend/src/test/server.ts` — MSW Node server export.
- `frontend/src/test/handlers.ts` — Base MSW handlers + `defaultUser` fixture.
- `frontend/src/test/renderWithProviders.tsx` — Provider-stack render helper (Chakra + QueryClient + MemoryRouter + AuthProvider).
- `frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx` — Five scenario tests for the banner.

**Modified:**
- `frontend/package.json` — Add `jsdom` and `msw` to devDependencies.
- `frontend/vite.config.ts` — Add Vitest type reference and `test:` block.
- `.github/workflows/ci.yml` — Uncomment frontend test step (lines 150-153).

---

## Task 1: Install dependencies and configure Vitest

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Cut a clean implementation branch from main**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git fetch origin
git checkout main
git pull --ff-only origin main
git checkout -b feat/frontend-component-testing
```

Expected: New branch `feat/frontend-component-testing` checked out, identical to `origin/main`.

- [ ] **Step 2: Install jsdom and msw as devDependencies**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker/frontend
npm install --save-dev jsdom@^24 msw@^2
```

Expected: `package.json` and `package-lock.json` updated. No errors. `node_modules/jsdom` and `node_modules/msw` exist.

- [ ] **Step 3: Add Vitest `test:` block to `vite.config.ts`**

Open `frontend/vite.config.ts`. At the very top of the file (line 1), add the triple-slash directive:

```ts
/// <reference types="vitest" />
```

Then, inside the `defineConfig({ ... })` object, add the `test:` block. Place it after the `server:` block (which is the last existing top-level key). The result should look like the snippet below:

```ts
  server: {
    host: true,
    port: 5173,
    watch: {
      usePolling: true,
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
```

- [ ] **Step 4: Verify Vitest discovers no tests yet (smoke check)**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker/frontend
npm test -- --run
```

Expected: Exits with `No test files found`. Vitest must not crash on the new config block. (If it crashes about a missing `./src/test/setup.ts`, that's fine — proceed to Task 2; the file is created next. If it crashes for any other reason, fix before proceeding.)

- [ ] **Step 5: Commit**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts
git commit -m "chore(frontend): add jsdom + msw devDeps and Vitest test config"
```

---

## Task 2: Create MSW server, handlers, and Vitest setup file

**Files:**
- Create: `frontend/src/test/handlers.ts`
- Create: `frontend/src/test/server.ts`
- Create: `frontend/src/test/setup.ts`

- [ ] **Step 1: Create the MSW handlers file**

Create `frontend/src/test/handlers.ts` with this exact content:

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

`*` at the start of the URL matches any host/base path so the handlers work whether Axios uses a relative URL or an absolute one.

- [ ] **Step 2: Create the MSW server file**

Create `frontend/src/test/server.ts` with this exact content:

```ts
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

- [ ] **Step 3: Create the Vitest setup file**

Create `frontend/src/test/setup.ts` with this exact content:

```ts
import '@testing-library/jest-dom/vitest'
import '@/i18n/config'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import { server } from './server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  localStorage.clear()
})
afterAll(() => server.close())
```

The `'@/i18n/config'` side-effect import initializes the global i18next instance (mirroring `main.tsx`); without it, anything calling `useTranslation` (including `AuthProvider`) crashes at render time. `localStorage.clear()` resets the auth token between tests so `AuthProvider` doesn't carry state across them.

- [ ] **Step 4: Verify the setup file loads cleanly**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker/frontend
npm test -- --run
```

Expected: `No test files found` (Vitest now successfully loads the setup file before discovering zero tests). Any error mentioning `setup.ts`, `msw`, or `i18n/config` means a misconfigured import — fix before proceeding.

- [ ] **Step 5: Commit**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git add frontend/src/test/handlers.ts frontend/src/test/server.ts frontend/src/test/setup.ts
git commit -m "test(frontend): add MSW server, base handlers, and Vitest setup file"
```

---

## Task 3: Create the `renderWithProviders` helper

**Files:**
- Create: `frontend/src/test/renderWithProviders.tsx`

- [ ] **Step 1: Create the helper file**

Create `frontend/src/test/renderWithProviders.tsx` with this exact content:

```tsx
import { ReactElement, ReactNode } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { ChakraProvider } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'

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

  const Wrapper = ({ children }: { children: ReactNode }) => {
    const tree = (
      <ChakraProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </QueryClientProvider>
      </ChakraProvider>
    )
    return withAuth ? <AuthProvider>{tree}</AuthProvider> : tree
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions })
}
```

Key points:
- Fresh `QueryClient` per call (so cache cannot leak across tests).
- `MemoryRouter` so we don't touch `window.location`.
- Real `AuthProvider` (not a mock) — because `localStorage` is empty in tests, it stays in unauthenticated mode and never hits `/auth/me`.

- [ ] **Step 2: Type-check passes**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker/frontend
npx tsc --noEmit --strict
```

Expected: Exits 0 with no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git add frontend/src/test/renderWithProviders.tsx
git commit -m "test(frontend): add renderWithProviders helper with full provider stack"
```

---

## Task 4: Banner test scenario 1 — visibility invariant

**Files:**
- Create: `frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx`

- [ ] **Step 1: Write the test file with the fixture factory and scenario 1**

Create `frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx` with this exact content:

```tsx
import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { CancellationSuggestionBanner } from './CancellationSuggestionBanner'
import { renderWithProviders } from '@/test/renderWithProviders'
import type { Subscription } from '@/types'

function buildSubscriptionWithSuggestion(
  overrides: Partial<Subscription> = {},
): Subscription {
  return {
    id: 'sub-1',
    user_id: 'test-user-id',
    mailbox_id: null,
    provider: 'Netflix',
    email_sender: null,
    amount: 12.99,
    currency: 'USD',
    billing_cycle: 'monthly',
    renewal_date: null,
    next_renewal_date: null,
    next_billing_date: null,
    is_active: true,
    category: 'streaming',
    tags: null,
    custom_label: null,
    notes: null,
    confidence_score: 0.95,
    extraction_method: 'ai',
    payment_processor: null,
    first_detected_at: '2026-01-01T00:00:00Z',
    last_confirmed_at: '2026-01-01T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    suggested_cancellation_status: 'cancelled',
    cancellation_suggestion_reason: 'Email confirms cancellation processed.',
    cancellation_suggestion_created_at: '2026-04-30T00:00:00Z',
    ...overrides,
  }
}

describe('CancellationSuggestionBanner', () => {
  it('renders nothing when no cancellation suggestion exists', () => {
    const subscription = buildSubscriptionWithSuggestion({
      suggested_cancellation_status: null,
      cancellation_suggestion_reason: null,
    })

    renderWithProviders(
      <CancellationSuggestionBanner
        subscription={subscription}
        onUpdate={() => {}}
      />,
    )

    expect(
      screen.queryByText('AI Detected Potential Cancellation'),
    ).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run the test and verify it passes**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker/frontend
npm test -- --run src/components/subscriptions/CancellationSuggestionBanner.test.tsx
```

Expected: 1 test passes. If the test fails because of an unhandled MSW request, the component is doing something unexpected on mount with no suggestion (it shouldn't be) — investigate.

- [ ] **Step 3: Commit**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git add frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx
git commit -m "test(banner): assert visibility invariant for cancellation suggestion"
```

---

## Task 5: Banner test scenario 2 — renders when suggestion present

**Files:**
- Modify: `frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx`

- [ ] **Step 1: Append the scenario 2 test**

Inside the existing `describe('CancellationSuggestionBanner', () => { ... })` block in `frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx`, add this `it` block immediately after the scenario 1 test:

```tsx
  it('renders the title, reason, and both action buttons when suggestion is present', () => {
    const subscription = buildSubscriptionWithSuggestion()

    renderWithProviders(
      <CancellationSuggestionBanner
        subscription={subscription}
        onUpdate={() => {}}
      />,
    )

    expect(
      screen.getByText('AI Detected Potential Cancellation'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Email confirms cancellation processed.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Accept & Mark as Cancelled' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Dismiss Suggestion' }),
    ).toBeInTheDocument()
  })
```

- [ ] **Step 2: Run both tests and verify they pass**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker/frontend
npm test -- --run src/components/subscriptions/CancellationSuggestionBanner.test.tsx
```

Expected: 2 tests pass.

- [ ] **Step 3: Commit**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git add frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx
git commit -m "test(banner): assert title, reason, and buttons render with suggestion"
```

---

## Task 6: Banner test scenario 3 — accept calls API and triggers `onUpdate`

**Files:**
- Modify: `frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx`

- [ ] **Step 1: Add the MSW + userEvent + vi imports at the top of the file**

In `frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx`, replace the existing import block at the top of the file with this expanded version:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { CancellationSuggestionBanner } from './CancellationSuggestionBanner'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { Subscription } from '@/types'
```

The `buildSubscriptionWithSuggestion` factory and existing `it` blocks below are unchanged.

- [ ] **Step 2: Append the scenario 3 test**

Inside the same `describe` block, after the scenario 2 `it`, add:

```tsx
  it('calls accept-suggestion endpoint and onUpdate when Accept is clicked', async () => {
    server.use(
      http.post('*/subscriptions/sub-1/accept-suggestion', () =>
        HttpResponse.json(buildSubscriptionWithSuggestion()),
      ),
    )
    const onUpdate = vi.fn()
    const user = userEvent.setup()

    renderWithProviders(
      <CancellationSuggestionBanner
        subscription={buildSubscriptionWithSuggestion()}
        onUpdate={onUpdate}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: 'Accept & Mark as Cancelled' }),
    )

    expect(await screen.findByText('Suggestion Accepted')).toBeInTheDocument()
    expect(onUpdate).toHaveBeenCalledTimes(1)
  })
```

The endpoint URL `*/subscriptions/sub-1/accept-suggestion` matches the real API route in `frontend/src/api/subscriptions.ts:113` (`/subscriptions/${id}/accept-suggestion`). The `sub-1` segment matches the fixture's `id`.

- [ ] **Step 3: Run all three tests and verify they pass**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker/frontend
npm test -- --run src/components/subscriptions/CancellationSuggestionBanner.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git add frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx
git commit -m "test(banner): assert accept click hits API and fires onUpdate"
```

---

## Task 7: Banner test scenario 4 — dismiss hides banner and triggers `onUpdate`

**Files:**
- Modify: `frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx`

- [ ] **Step 1: Append the scenario 4 test**

Inside the same `describe` block, after the scenario 3 `it`, add:

```tsx
  it('calls dismiss-suggestion endpoint, hides the banner, and fires onUpdate when Dismiss is clicked', async () => {
    server.use(
      http.post('*/subscriptions/sub-1/dismiss-suggestion', () =>
        HttpResponse.json({ success: true, message: 'dismissed' }),
      ),
    )
    const onUpdate = vi.fn()
    const user = userEvent.setup()

    renderWithProviders(
      <CancellationSuggestionBanner
        subscription={buildSubscriptionWithSuggestion()}
        onUpdate={onUpdate}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: 'Dismiss Suggestion' }),
    )

    expect(await screen.findByText('Suggestion Dismissed')).toBeInTheDocument()
    expect(
      screen.queryByText('AI Detected Potential Cancellation'),
    ).not.toBeInTheDocument()
    expect(onUpdate).toHaveBeenCalledTimes(1)
  })
```

The endpoint URL matches `frontend/src/api/subscriptions.ts:118` (`/subscriptions/${id}/dismiss-suggestion`). The component's `handleDismiss` sets `isVisible=false` and calls `onUpdate()` after the API resolves; the assertions verify all three side effects.

- [ ] **Step 2: Run all four tests and verify they pass**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker/frontend
npm test -- --run src/components/subscriptions/CancellationSuggestionBanner.test.tsx
```

Expected: 4 tests pass.

- [ ] **Step 3: Commit**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git add frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx
git commit -m "test(banner): assert dismiss click hits API, hides banner, fires onUpdate"
```

---

## Task 8: Banner test scenario 5 — accept failure shows error toast and skips `onUpdate`

**Files:**
- Modify: `frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx`

- [ ] **Step 1: Append the scenario 5 test**

Inside the same `describe` block, after the scenario 4 `it`, add:

```tsx
  it('shows an error toast and does not call onUpdate when accept fails', async () => {
    server.use(
      http.post('*/subscriptions/sub-1/accept-suggestion', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    const onUpdate = vi.fn()
    const user = userEvent.setup()

    renderWithProviders(
      <CancellationSuggestionBanner
        subscription={buildSubscriptionWithSuggestion()}
        onUpdate={onUpdate}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: 'Accept & Mark as Cancelled' }),
    )

    expect(
      await screen.findByText('Failed to accept cancellation suggestion.'),
    ).toBeInTheDocument()
    expect(onUpdate).not.toHaveBeenCalled()
  })
```

Asserts the toast description text (the title "Error" is a generic word that may collide with other DOM content; the description is unique to this code path).

- [ ] **Step 2: Run all five tests and verify they pass**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker/frontend
npm test -- --run src/components/subscriptions/CancellationSuggestionBanner.test.tsx
```

Expected: 5 tests pass.

- [ ] **Step 3: Commit**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git add frontend/src/components/subscriptions/CancellationSuggestionBanner.test.tsx
git commit -m "test(banner): assert accept failure surfaces error toast and skips onUpdate"
```

---

## Task 9: Re-enable the CI test step

**Files:**
- Modify: `.github/workflows/ci.yml` (lines 150-153)

- [ ] **Step 1: Verify the full frontend pipeline passes locally before touching CI**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker/frontend
npm run lint && npx tsc --noEmit --strict && npm test -- --run && npm run build
```

Expected: All four commands exit 0. If any fails, fix before changing CI — don't push a known-broken pipeline.

- [ ] **Step 2: Replace the commented-out test block with a live step**

Open `.github/workflows/ci.yml`. Find the block at lines 150-153:

```yaml
      # Tests temporarily disabled - will be fixed in separate PR
      # - name: Run tests
      #   working-directory: frontend
      #   run: npm test -- --run
```

Replace it with:

```yaml
      - name: Run unit tests
        working-directory: frontend
        run: npm test -- --run
```

- [ ] **Step 3: Commit**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git add .github/workflows/ci.yml
git commit -m "ci: re-enable frontend unit tests in Frontend Quality job"
```

- [ ] **Step 4: Push the branch and open a PR**

```bash
cd /Users/fabienmartinez/Documents/workspace/perso/projects/claude_projects/subscription_tracker
git push -u origin feat/frontend-component-testing
gh pr create --title "feat(frontend): component testing infrastructure + banner tests" --body "$(cat <<'EOF'
## Summary
- Stand up Vitest + jsdom + MSW frontend test environment with a shared `renderWithProviders` helper
- Add 5 tests for `CancellationSuggestionBanner` covering visibility, accept, dismiss, and error paths
- Re-enable the `Run unit tests` step in `.github/workflows/ci.yml` (was commented out since the original scaffolding was deferred)

Spec: `docs/superpowers/specs/2026-05-03-frontend-component-testing-design.md`

## Test plan
- [ ] CI: Frontend Quality & Security job is green (lint, tsc, unit tests, build)
- [ ] Local: `cd frontend && npm test -- --run` shows 5 passing tests
- [ ] Local: `cd frontend && npx tsc --noEmit --strict` exits 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Verify CI is green**

After the PR is open, watch the `Frontend Quality & Security` job. Expected: all steps pass, including the new `Run unit tests` step. If it fails, capture the failure output and fix before merging.

---

## Done criteria

- 5 new test files / module files exist under `frontend/src/test/` and `frontend/src/components/subscriptions/`.
- `npm test -- --run` from `frontend/` reports 5 passing tests in <5 s.
- `npx tsc --noEmit --strict` exits 0.
- CI's Frontend Quality & Security job is green on the PR.
- The PR is ready for review.
