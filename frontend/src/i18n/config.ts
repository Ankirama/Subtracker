import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import enCommon from '../locales/en/common.json'
import enAuth from '../locales/en/auth.json'
import enSubscriptions from '../locales/en/subscriptions.json'
import enSettings from '../locales/en/settings.json'
import enErrors from '../locales/en/errors.json'

import frCommon from '../locales/fr/common.json'
import frAuth from '../locales/fr/auth.json'
import frSubscriptions from '../locales/fr/subscriptions.json'
import frSettings from '../locales/fr/settings.json'
import frErrors from '../locales/fr/errors.json'

const resources = {
  en: {
    common: enCommon,
    auth: enAuth,
    subscriptions: enSubscriptions,
    settings: enSettings,
    errors: enErrors,
  },
  fr: {
    common: frCommon,
    auth: frAuth,
    subscriptions: frSubscriptions,
    settings: frSettings,
    errors: frErrors,
  },
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    defaultNS: 'common',
    ns: ['common', 'auth', 'subscriptions', 'settings', 'errors'],

    interpolation: {
      escapeValue: false, // React already escapes values
    },

    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },

    react: {
      useSuspense: true,
    },
  })

export default i18n
