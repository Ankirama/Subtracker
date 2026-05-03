import '@testing-library/jest-dom/vitest'
import '@/i18n/config'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import { server } from './server'

// jsdom storage implementation compatibility fix
// Both Node 20 and 25 require explicit localStorage setup in jsdom
if (typeof window !== 'undefined' && typeof localStorage === 'object' && !localStorage.getItem) {
  const store: Record<string, string> = {}
  const handler: ProxyHandler<Record<string, string>> = {
    get: (target, prop: string | symbol) => {
      if (prop === 'length') return Object.keys(target).length
      if (typeof prop === 'string') {
        if (prop === 'getItem') return (key: string) => target[key] ?? null
        if (prop === 'setItem') return (key: string, value: string) => { target[key] = value }
        if (prop === 'removeItem') return (key: string) => { delete target[key] }
        if (prop === 'clear') return () => { Object.keys(target).forEach((k) => { delete target[k] }) }
        if (prop === 'key') return (index: number) => Object.keys(target)[index] ?? null
      }
      return target[prop as keyof typeof target]
    },
  }
  Object.defineProperty(window, 'localStorage', {
    value: new Proxy(store, handler),
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
