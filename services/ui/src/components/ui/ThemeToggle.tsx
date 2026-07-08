import type { ReactNode } from 'react'
import { Moon, Sun, Monitor } from 'lucide-react'
import { useTheme, type Theme } from '../../hooks/useTheme'

const icons: Record<Theme, ReactNode> = {
  light: <Sun size={16} aria-hidden />,
  dark: <Moon size={16} aria-hidden />,
  system: <Monitor size={16} aria-hidden />,
}

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
  const { theme, toggle } = useTheme()

  return (
    <button
      onClick={toggle}
      className={`inline-flex items-center gap-2 rounded-lg px-2.5 py-2 text-text-muted hover:text-text hover:bg-surface-2 transition-colors ${className}`}
      title={`Theme: ${labels[theme]}`}
      aria-label={`Current theme: ${labels[theme]}. Click to change.`}
    >
      {icons[theme]}
      {showLabel && <span className="text-sm">{labels[theme]}</span>}
    </button>
  )
}
