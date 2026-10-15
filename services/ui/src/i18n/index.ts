/**
 * i18n setup.
 *
 * English is the key set: components call `t('Save changes')`, not
 * `t('settings.save')`. A string with no Russian entry therefore renders as
 * correct English rather than as a raw key — the right failure for a feature
 * whose first pass deliberately covers only part of a 229-file UI.
 *
 * That choice constrains the parser: English sentences contain `.`, `:` and
 * `,`, which i18next otherwise reads as namespace and nesting separators, so
 * both are turned off and every lookup is a flat key in one namespace.
 */
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from '../locales/en/common.json'

/** Tags the app ships, mirroring `settings_service.SUPPORTED_LANGUAGES`. */
export const SUPPORTED_LANGUAGES = ['en', 'ru'] as const
export type Language = (typeof SUPPORTED_LANGUAGES)[number]

/** What each language calls itself — a menu of languages reads in its own. */
export const LANGUAGE_LABELS: Record<Language, string> = {
  en: 'English',
  ru: 'Русский',
}

export const DEFAULT_LANGUAGE: Language = 'en'

export const LANGUAGE_STORAGE_KEY = 'studyaio-language'

export function isLanguage(value: unknown): value is Language {
  return typeof value === 'string' && (SUPPORTED_LANGUAGES as readonly string[]).includes(value)
}

/**
 * The language to paint with before the settings query resolves.
 *
 * The server stays authoritative — this only avoids a flash of English for
 * someone who has already chosen otherwise, exactly as `useTheme` does.
 */
export function getStoredLanguage(): Language {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY)
    if (isLanguage(stored)) return stored
  } catch {
    /* private mode, or storage disabled */
  }
  return DEFAULT_LANGUAGE
}

/**
 * Loads a non-English bundle on demand. Russian is ~130 KB of JSON that an
 * English session never reads, so it is a separate chunk fetched when the
 * language is first selected (at boot for a stored choice, see `i18nReady`).
 * `changeLanguage` resolves only after the bundle is in, so callers that
 * await it see the new language immediately.
 */
const lazyLocales: Record<Exclude<Language, 'en'>, () => Promise<{ default: Record<string, string> }>> = {
  ru: () => import('../locales/ru/common.json'),
}

const lazyBackend = {
  type: 'backend' as const,
  init() {},
  read(
    language: string,
    _namespace: string,
    callback: (err: Error | null, data?: Record<string, string>) => void,
  ) {
    const load = lazyLocales[language as keyof typeof lazyLocales]
    if (!load) {
      callback(null, {})
      return
    }
    load().then(
      (mod) => callback(null, mod.default),
      (err: unknown) => callback(err instanceof Error ? err : new Error(String(err))),
    )
  },
}

/** Resolves once the initial language's bundle is loaded; await before first render. */
export const i18nReady: Promise<unknown> = i18n.use(lazyBackend).use(initReactI18next).init({
  // English lives in the keys, so its bundle holds only what a key cannot
  // express on its own: the plural forms. Without them a count key renders
  // as written — "5 course" — for the language the keys are authored in.
  resources: { en: { common: en } },
  partialBundledLanguages: true,
  lng: getStoredLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  defaultNS: 'common',
  ns: ['common'],
  keySeparator: false,
  nsSeparator: false,
  // An empty Russian string means "not translated yet", not "render nothing".
  returnEmptyString: false,
  interpolation: { escapeValue: false },
})

export default i18n
