/**
 * Provider logo utilities using Clearbit Logo API
 * Free service that provides company logos based on domain
 */

import { API_BASE_URL } from '../api/client'

// Common provider domain mappings
export const PROVIDER_DOMAINS: Record<string, string> = {
  // Streaming
  'netflix': 'netflix.com',
  'spotify': 'spotify.com',
  'youtube': 'youtube.com',
  'disney': 'disneyplus.com',
  'hbo': 'hbo.com',
  'prime video': 'primevideo.com',
  'amazon prime': 'amazon.com',
  'apple tv': 'apple.com',
  'hulu': 'hulu.com',
  'paramount': 'paramountplus.com',

  // Software & Tools
  'adobe': 'adobe.com',
  'microsoft': 'microsoft.com',
  'apple': 'apple.com',
  'google': 'google.com',
  'dropbox': 'dropbox.com',
  'github': 'github.com',
  'notion': 'notion.so',
  'figma': 'figma.com',
  'canva': 'canva.com',
  'slack': 'slack.com',
  'zoom': 'zoom.us',
  'asana': 'asana.com',
  'trello': 'trello.com',
  'monday': 'monday.com',

  // Cloud & Hosting
  'aws': 'aws.amazon.com',
  'azure': 'azure.microsoft.com',
  'google cloud': 'cloud.google.com',
  'vercel': 'vercel.com',
  'netlify': 'netlify.com',
  'heroku': 'heroku.com',
  'digitalocean': 'digitalocean.com',

  // Social Media
  'linkedin': 'linkedin.com',
  'twitter': 'twitter.com',
  'facebook': 'facebook.com',
  'instagram': 'instagram.com',
  'tiktok': 'tiktok.com',

  // Productivity
  'office 365': 'microsoft.com',
  'google workspace': 'google.com',
  'evernote': 'evernote.com',
  'lastpass': 'lastpass.com',
  '1password': '1password.com',
  'dashlane': 'dashlane.com',

  // Email & Marketing
  'mailchimp': 'mailchimp.com',
  'sendgrid': 'sendgrid.com',
  'constant contact': 'constantcontact.com',
  'hubspot': 'hubspot.com',

  // E-commerce
  'shopify': 'shopify.com',
  'woocommerce': 'woocommerce.com',
  'square': 'squareup.com',

  // Payment
  'stripe': 'stripe.com',
  'paypal': 'paypal.com',

  // Communication
  'whatsapp': 'whatsapp.com',
  'telegram': 'telegram.org',
  'discord': 'discord.com',
}

/**
 * Get logo URL for a provider using our backend proxy
 * This avoids ad blocker issues by serving logos from our own domain
 */
export const getProviderLogoUrl = (providerName: string): string | null => {
  if (!providerName) return null

  // Use our backend endpoint which downloads and caches logos
  // API_BASE_URL already includes /api, so we just add /providers
  return `${API_BASE_URL}/providers/${encodeURIComponent(providerName)}/logo`
}

/**
 * Get provider initials for fallback display
 */
export const getProviderInitials = (providerName: string): string => {
  const words = providerName.trim().split(/\s+/)

  if (words.length === 1) {
    // Single word: take first 2 letters
    return providerName.substring(0, 2).toUpperCase()
  }

  // Multiple words: take first letter of each word (max 2)
  return words
    .slice(0, 2)
    .map(word => word[0])
    .join('')
    .toUpperCase()
}
