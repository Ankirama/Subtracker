/**
 * Language detection utilities for i18n
 *
 * Priority order:
 * 1. User preference from database (fetched on login)
 * 2. localStorage (i18nextLng key)
 * 3. Browser language (navigator.language)
 * 4. Fallback to English
 */

const SUPPORTED_LANGUAGES = ['en', 'fr'] as const
export type SupportedLanguage = typeof SUPPORTED_LANGUAGES[number]

/**
 * Detect browser language and map to supported languages
 */
export const detectBrowserLanguage = (): SupportedLanguage => {
  const browserLang = navigator.language.split('-')[0].toLowerCase()

  if (SUPPORTED_LANGUAGES.includes(browserLang as SupportedLanguage)) {
    return browserLang as SupportedLanguage
  }

  return 'en'
}

/**
 * Get the current language from localStorage or browser
 */
export const getCurrentLanguage = (): SupportedLanguage => {
  const storedLang = localStorage.getItem('i18nextLng')

  if (storedLang && SUPPORTED_LANGUAGES.includes(storedLang as SupportedLanguage)) {
    return storedLang as SupportedLanguage
  }

  return detectBrowserLanguage()
}

/**
 * Set language in both i18n and localStorage
 */
export const setLanguage = (lang: SupportedLanguage): void => {
  localStorage.setItem('i18nextLng', lang)
}

/**
 * Sync user preference from database to i18n
 * Called after login or when user updates preference
 */
export const syncUserLanguagePreference = async (preferredLanguage: string | null): Promise<void> => {
  if (preferredLanguage && SUPPORTED_LANGUAGES.includes(preferredLanguage as SupportedLanguage)) {
    setLanguage(preferredLanguage as SupportedLanguage)
    // i18n will automatically pick up the change from localStorage
  }
}

export { SUPPORTED_LANGUAGES }
