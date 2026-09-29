import { useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  DEFAULT_LANGUAGE,
  LANGUAGE_STORAGE_KEY,
  isLanguage,
  type Language,
} from '../i18n'
import { useSettings, useUpdateSettings } from './useApi'

function storeLanguage(language: Language) {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
  } catch {
    /* private mode, or storage disabled */
  }
}

/**
 * The user's language preference, and how far it reaches.
 *
 * The server is authoritative: `user_settings` is what follows the account to
 * another browser. `localStorage` only mirrors it, so the first paint before
 * the settings query resolves is not in the wrong language — the same split
 * `useTheme` uses.
 */
export function useLanguage() {
  const { i18n } = useTranslation()
  const { data: settings } = useSettings()
  const updateSettings = useUpdateSettings()

  const language: Language = isLanguage(i18n.language) ? i18n.language : DEFAULT_LANGUAGE
  const serverLanguage = settings?.language

  // Adopt the stored preference once it arrives, and whenever it changes
  // elsewhere (another tab, another device).
  useEffect(() => {
    if (isLanguage(serverLanguage) && serverLanguage !== i18n.language) {
      void i18n.changeLanguage(serverLanguage)
      storeLanguage(serverLanguage)
    }
  }, [serverLanguage, i18n])

  // Assistive technology and the browser's own UI read this.
  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  const setLanguage = useCallback(
    (next: Language) => {
      void i18n.changeLanguage(next)
      storeLanguage(next)
      updateSettings.mutate({ language: next })
    },
    [i18n, updateSettings],
  )

  const setContentLanguage = useCallback(
    (enabled: boolean) => {
      updateSettings.mutate({ content_language: enabled })
    },
    [updateSettings],
  )

  return {
    language,
    /** Whether AI-generated study material is written in `language` too. */
    contentLanguage: settings?.content_language ?? false,
    setLanguage,
    setContentLanguage,
    isSaving: updateSettings.isPending,
  } as const
}
