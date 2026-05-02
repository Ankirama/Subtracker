import { describe, expect, it } from 'vitest'
import {
  capitalize,
  formatBillingCycle,
  formatCurrency,
  formatPercentage,
} from './formatters'

describe('formatCurrency', () => {
  it('returns "-" for null or undefined amounts', () => {
    expect(formatCurrency(null)).toBe('-')
    expect(formatCurrency(undefined)).toBe('-')
  })

  it('formats USD with a leading dollar sign and two decimals', () => {
    expect(formatCurrency(9.99, 'USD')).toBe('$9.99')
  })

  it('uses EUR by default', () => {
    expect(formatCurrency(10)).toContain('10.00')
  })
})

describe('formatBillingCycle', () => {
  it('maps known cycles to their human label', () => {
    expect(formatBillingCycle('monthly')).toBe('Monthly')
    expect(formatBillingCycle('yearly')).toBe('Yearly')
    expect(formatBillingCycle('bi-weekly')).toBe('Bi-weekly')
  })

  it('returns the input unchanged for unknown cycles', () => {
    expect(formatBillingCycle('lunar')).toBe('lunar')
  })
})

describe('formatPercentage', () => {
  it('returns "-" for null or undefined', () => {
    expect(formatPercentage(null)).toBe('-')
    expect(formatPercentage(undefined)).toBe('-')
  })

  it('rounds to the requested decimal precision', () => {
    expect(formatPercentage(50.123, 1)).toBe('50.1%')
    expect(formatPercentage(50, 0)).toBe('50%')
  })
})

describe('capitalize', () => {
  it('uppercases the first character and lowercases the rest', () => {
    expect(capitalize('hello')).toBe('Hello')
    expect(capitalize('WORLD')).toBe('World')
  })

  it('returns an empty string when given an empty input', () => {
    expect(capitalize('')).toBe('')
  })
})
