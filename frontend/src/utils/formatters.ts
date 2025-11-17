/**
 * Utility functions for formatting currency, dates, and other values
 */

/**
 * Format a number as currency with the specified currency code
 */
export const formatCurrency = (amount: number | null | undefined, currency: string = 'EUR'): string => {
  if (amount === null || amount === undefined) {
    return '-'
  }

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

/**
 * Format a date string to a localized date/time format
 */
export const formatDate = (dateString: string | null | undefined): string => {
  if (!dateString) {
    return '-'
  }

  return new Date(dateString).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Format a date string to a short date format (no time)
 */
export const formatDateShort = (dateString: string | null | undefined): string => {
  if (!dateString) {
    return '-'
  }

  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Format a number as a percentage
 */
export const formatPercentage = (value: number | null | undefined, decimals: number = 1): string => {
  if (value === null || value === undefined) {
    return '-'
  }

  return `${value.toFixed(decimals)}%`
}

/**
 * Format a billing cycle to a human-readable string
 */
export const formatBillingCycle = (cycle: string): string => {
  const cycleMap: Record<string, string> = {
    'weekly': 'Weekly',
    'bi-weekly': 'Bi-weekly',
    'monthly': 'Monthly',
    'quarterly': 'Quarterly',
    'semi-annual': 'Semi-annual',
    'yearly': 'Yearly',
    'annual': 'Annual',
  }

  return cycleMap[cycle.toLowerCase()] || cycle
}

/**
 * Capitalize the first letter of a string
 */
export const capitalize = (str: string): string => {
  if (!str) return ''
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase()
}
