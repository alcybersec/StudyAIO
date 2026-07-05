import { Card, Button } from '../../ui'
import { useTheme, type Theme } from '../../../hooks/useTheme'
import { useTour } from '../../../hooks/useTour'

const THEMES: Theme[] = ['light', 'dark', 'system']

/** Appearance settings: theme choice (applies instantly) and the onboarding tour replay. */
export function AppearanceSection() {
  const { theme, setTheme } = useTheme()
  const { replay: replayTour } = useTour()

  return (
    <Card>
      <h2 className="text-[13px] font-semibold text-text mb-4">Appearance</h2>
      <div className="space-y-5 max-w-md">
        <div>
          <span className="block text-xs font-medium text-text-muted mb-1.5">Theme</span>
          <div className="flex items-center gap-2" role="group" aria-label="Theme">
            {THEMES.map((t) => (
              <button
                key={t}
                type="button"
                aria-pressed={theme === t}
                onClick={() => setTheme(t)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors min-h-[44px] cursor-pointer ${
                  theme === t
                    ? 'bg-sage text-on-accent'
                    : 'bg-surface-2 text-text-muted hover:text-text hover:bg-surface-2/70'
                }`}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-text-faint">
            Choose how StudyAIO looks. System follows your OS preference.
          </p>
        </div>

        <div>
          <span className="block text-xs font-medium text-text-muted mb-1.5">Onboarding tour</span>
          <Button variant="secondary" size="sm" onClick={replayTour}>
            Replay tour
          </Button>
          <p className="mt-1.5 text-xs text-text-faint">
            Walk through the app's main features with a guided tour.
          </p>
        </div>
      </div>
    </Card>
  )
}
