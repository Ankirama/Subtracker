import '@testing-library/jest-dom/vitest'
import '@/i18n/config'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import { server } from './server'

// Node 25 exposes a native (stub) localStorage that lacks full Storage methods.
// Extract jsdom's implementation from the internal dom object and override globalThis
// so localStorage.clear() and other methods work correctly in tests.
const jsdomInstance = (globalThis as unknown as { jsdom?: { window?: { _localStorage?: Storage } } }).jsdom
if (jsdomInstance?.window?._localStorage) {
  Object.defineProperty(globalThis, 'localStorage', {
    value: jsdomInstance.window._localStorage,
    writable: true,
    configurable: true,
  })
}

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  localStorage.clear()
})
afterAll(() => server.close())
