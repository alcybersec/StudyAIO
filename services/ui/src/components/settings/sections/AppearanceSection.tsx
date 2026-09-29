import { useTranslation } from 'react-i18next'
import { Card, Button } from '../../ui'
import { useTheme, type Theme } from '../../../hooks/useTheme'
import { useTour } from '../../../hooks/useTour'
import { useLanguage } from '../../../hooks/useLanguage'
import { LANGUAGE_LABELS, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE } from '../../../i18n'

const THEMES: Theme[] = ['light', 'dark', 'system']

const THEME_LABELS: Record<Theme, string> = {
  light: 'Light',
  dark: 'Dark',
  system: 'System',
}

/** Appearance settings: theme, language (both apply instantly) and the tour replay. */
export function AppearanceSection() {
  const { t } = useTranslation()
  const { theme, setTheme } = useTheme()
  const { language, contentLanguage, setLanguage, setContentLanguage, isSaving } = useLanguage()
  const { replay: replayTour } = useTour()

  // "Also generate content in English" is the behaviour English already has,
  // so offering it as a switch would imply a choice that does nothing.
  const contentToggleAvailable = language !== DEFAULT_LANGUAGE

  return (
    <Card>
      <h2 className="text-[13px] font-semibold text-text mb-4">{t('Appearance')}</h2>
      <div className="space-y-5 max-w-md">
        <div>
          <span className="block text-xs font-medium text-text-muted mb-1.5">{t('Theme')}</span>
          <div className="flex items-center gap-2" role="group" aria-label={t('Theme')}>
            {THEMES.map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={theme === option}
                onClick={() => setTheme(option)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors min-h-[44px] cursor-pointer ${
                  theme === option
                    ? 'bg-sage text-on-accent'
                    : 'bg-surface-2 text-text-muted hover:text-text hover:bg-surface-2/70'
                }`}
              >
                {t(THEME_LABELS[option])}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-text-faint">
            {t('Choose how StudyAIO looks. System follows your OS preference.')}
          </p>
        </div>

        <div>
          <span className="block text-xs font-medium text-text-muted mb-1.5">{t('Language')}</span>
          <div className="flex items-center gap-2" role="group" aria-label={t('Language')}>
            {SUPPORTED_LANGUAGES.map((option) => (
              <button
                key={option}
                type="button"
                lang={option}
                aria-pressed={language === option}
                disabled={isSaving}
                onClick={() => setLanguage(option)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors min-h-[44px] cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed ${
                  language === option
                    ? 'bg-sage text-on-accent'
                    : 'bg-surface-2 text-text-muted hover:text-text hover:bg-surface-2/70'
                }`}
              >
                {/* Each language names itself, so it is readable to the person
                    looking for it. */}
                {LANGUAGE_LABELS[option]}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-text-faint">
            {t('The language of the interface, applied everywhere in the app.')}
          </p>

          <label className="mt-3 flex items-start gap-2.5 cursor-pointer has-disabled:cursor-not-allowed">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-sage cursor-pointer disabled:cursor-not-allowed"
              checked={contentLanguage}
              disabled={!contentToggleAvailable || isSaving}
              onChange={(e) => setContentLanguage(e.target.checked)}
            />
            <span>
              <span className="block text-xs font-medium text-text">
                {t('Also generate study material in this language')}
              </span>
              <span className="block mt-0.5 text-xs text-text-faint">
                {contentToggleAvailable
                  ? t('New summaries, flashcards, quizzes and chat answers are written in this language. Material already generated is unchanged.')
                  : t('Available once you choose a language other than English.')}
              </span>
            </span>
          </label>
        </div>

        <div>
          <span className="block text-xs font-medium text-text-muted mb-1.5">
            {t('Onboarding tour')}
          </span>
          <Button variant="secondary" size="sm" onClick={replayTour}>
            {t('Replay tour')}
          </Button>
          <p className="mt-1.5 text-xs text-text-faint">
            {t("Walk through the app's main features with a guided tour.")}
          </p>
        </div>
      </div>
    </Card>
  )
}
