import { describe, expect, it } from 'vitest'
import {
  BILLING_CYCLE_OPTIONS,
  BUDGET_PERIOD_OPTIONS,
  CURRENCIES,
  MAILBOX_SYNC_FREQUENCY_OPTIONS,
  NOTIFICATION_TYPE_ICONS,
} from './enums'

describe('BILLING_CYCLE_OPTIONS', () => {
  it('includes the five canonical subscription billing cycles', () => {
    const values = BILLING_CYCLE_OPTIONS.map((o) => o.value)
    expect(values).toEqual(['monthly', 'yearly', 'quarterly', 'weekly', 'one-time'])
  })

  it('pairs each value with a non-empty label', () => {
    for (const { value, label } of BILLING_CYCLE_OPTIONS) {
      expect(label.length).toBeGreaterThan(0)
      expect(value).not.toBe('')
    }
  })
})

describe('BUDGET_PERIOD_OPTIONS', () => {
  it('exposes monthly, quarterly, yearly in that order', () => {
    expect(BUDGET_PERIOD_OPTIONS.map((o) => o.value)).toEqual([
      'monthly',
      'quarterly',
      'yearly',
    ])
  })
})

describe('MAILBOX_SYNC_FREQUENCY_OPTIONS', () => {
  it('exposes manual, daily, weekly', () => {
    expect(MAILBOX_SYNC_FREQUENCY_OPTIONS.map((o) => o.value)).toEqual([
      'manual',
      'daily',
      'weekly',
    ])
  })
})

describe('CURRENCIES', () => {
  it('lists the six supported currencies with code/name/symbol', () => {
    expect(CURRENCIES.map((c) => c.code)).toEqual([
      'USD',
      'EUR',
      'GBP',
      'JPY',
      'CAD',
      'AUD',
    ])
    for (const { code, name, symbol } of CURRENCIES) {
      expect(code).toMatch(/^[A-Z]{3}$/)
      expect(name).not.toBe('')
      expect(symbol).not.toBe('')
    }
  })
})

describe('NOTIFICATION_TYPE_ICONS', () => {
  it('has a non-empty icon for every NotificationType key', () => {
    for (const [key, icon] of Object.entries(NOTIFICATION_TYPE_ICONS)) {
      expect(key).not.toBe('')
      expect(icon).not.toBe('')
    }
  })

  it('covers all 12 notification types', () => {
    expect(Object.keys(NOTIFICATION_TYPE_ICONS)).toHaveLength(12)
  })
})
