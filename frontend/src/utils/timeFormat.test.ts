import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { formatDistanceToNow } from './timeFormat'

describe('formatDistanceToNow', () => {
  const NOW = new Date('2026-01-15T12:00:00Z')

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns "just now" for sub-minute deltas', () => {
    const tenSecondsAgo = new Date(NOW.getTime() - 10_000)
    expect(formatDistanceToNow(tenSecondsAgo)).toBe('just now')
  })

  it('pluralizes minutes correctly', () => {
    const oneMinuteAgo = new Date(NOW.getTime() - 60_000)
    const fiveMinutesAgo = new Date(NOW.getTime() - 5 * 60_000)
    expect(formatDistanceToNow(oneMinuteAgo)).toBe('1 minute ago')
    expect(formatDistanceToNow(fiveMinutesAgo)).toBe('5 minutes ago')
  })

  it('falls back to days when the delta crosses 24 hours', () => {
    const threeDaysAgo = new Date(NOW.getTime() - 3 * 24 * 60 * 60 * 1000)
    expect(formatDistanceToNow(threeDaysAgo)).toBe('3 days ago')
  })

  it('accepts ISO date strings as input', () => {
    const oneHourAgo = new Date(NOW.getTime() - 60 * 60 * 1000).toISOString()
    expect(formatDistanceToNow(oneHourAgo)).toBe('1 hour ago')
  })
})
