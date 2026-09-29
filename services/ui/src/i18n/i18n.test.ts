/**
 * The i18n contract, not the translations themselves.
 *
 * English is the key set, which buys one specific property: a string with no
 * Russian entry renders as correct English rather than as a raw key. That is
 * what makes shipping a partial translation safe, so it is tested rather than
 * assumed.
 */
import { afterEach, describe, expect, it } from 'vitest'
import i18n, { SUPPORTED_LANGUAGES, LANGUAGE_LABELS, isLanguage } from './index'
import ru from '../locales/ru/common.json'

afterEach(async () => {
  await i18n.changeLanguage('en')
})

describe('supported languages', () => {
  it('mirrors the server list', () => {
    // settings_service.SUPPORTED_LANGUAGES — a tag the UI offers and the API
    // rejects would be a save that silently fails.
    expect([...SUPPORTED_LANGUAGES]).toEqual(['en', 'ru'])
  })

  it('labels each language in its own language', () => {
    expect(LANGUAGE_LABELS.ru).toBe('Русский')
  })

  it('rejects an unknown tag', () => {
    expect(isLanguage('ru')).toBe(true)
    expect(isLanguage('xx')).toBe(false)
    expect(isLanguage(undefined)).toBe(false)
  })
})

describe('translation', () => {
  it('returns Russian for a translated key', async () => {
    await i18n.changeLanguage('ru')
    expect(i18n.t('Settings')).toBe('Настройки')
  })

  it('falls back to English for an untranslated key, not to the raw key', async () => {
    await i18n.changeLanguage('ru')
    const untranslated = 'A screen this pass did not reach'

    // The whole point of authoring keys in English: partial coverage degrades
    // to readable English instead of showing a key to the user.
    expect(i18n.t(untranslated)).toBe(untranslated)
    expect(ru).not.toHaveProperty(untranslated)
  })

  it('renders English as written', () => {
    expect(i18n.t('Settings')).toBe('Settings')
  })

  it('does not split keys on the punctuation English sentences contain', () => {
    // Keys are whole sentences; `.` and `:` must not be read as namespace or
    // nesting separators, or every such lookup would miss.
    expect(i18n.t('Page not found')).toBe('Page not found')
    expect(i18n.options.keySeparator).toBe(false)
    expect(i18n.options.nsSeparator).toBe(false)
  })
})

describe('plurals', () => {
  it('pluralises English despite the key being singular', () => {
    expect(i18n.t('{{count}} course', { count: 1 })).toBe('1 course')
    expect(i18n.t('{{count}} course', { count: 3 })).toBe('3 courses')
  })

  it('uses the three Russian plural forms', async () => {
    await i18n.changeLanguage('ru')
    expect(i18n.t('{{count}} course', { count: 1 })).toBe('1 курс')
    expect(i18n.t('{{count}} course', { count: 3 })).toBe('3 курса')
    expect(i18n.t('{{count}} course', { count: 8 })).toBe('8 курсов')
  })
})
