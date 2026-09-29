import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Moon, Sun, Monitor } from 'lucide-react'
import { useTheme, type Theme } from '../../hooks/useTheme'

const icons: Record<Theme, ReactNode> = {
  light: <Sun size={16} aria-hidden />,
  dark: <Moon size={16} aria-hidden />,
  system: <Monitor size={16} aria-hidden />,
}

//: Keys, not display text — translated at the render site below.
const labels: Record<Theme, string> = {
  light: 'Light',
  dark: 'Dark',
  system: 'System',
}

interface ThemeToggleProps {
  showLabel?: boolean
  className?: string
}

export function ThemeToggle({ showLabel = false, className = '' }: ThemeToggleProps) {
  const { t } = useTranslation()
  const { theme, toggle } = useTheme()

  return (
    <button
      onClick={toggle}
      className={`inline-flex items-center gap-2 rounded-lg px-2.5 py-2 text-text-muted hover:text-text hover:bg-surface-2 transition-colors ${className}`}
      title={t('Theme: {{theme}}', { theme: t(labels[theme]) })}
      aria-label={t('Current theme: {{theme}}. Click to change.', { theme: t(labels[theme]) })}
    >
      {icons[theme]}
      {showLabel && <span className="text-sm">{t(labels[theme])}</span>}
    </button>
  )
}
