import { useTranslation } from 'react-i18next'
interface XPBarProps {
  level: number
  totalXP: number
  progressPct: number
  nextThreshold: number | null
}

export function XPBar({ level, totalXP, progressPct, nextThreshold }: XPBarProps) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-peri-soft text-peri-fg font-bold text-sm">
        {level}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="font-medium text-text">{t('Level {{level}}', { level })}</span>
          <span className="text-text-muted font-mono text-[11px]">
            {nextThreshold !== null
          ? t('{{xp}} XP / {{next}}', {
              xp: totalXP.toLocaleString(),
              next: nextThreshold.toLocaleString(),
            })
          : t('{{xp}} XP', { xp: totalXP.toLocaleString() })}
          </span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-surface-2 overflow-hidden">
          <div
            className="h-full rounded-full bg-peri transition-all duration-500 ease-out"
            style={{ width: `${Math.min(progressPct, 100)}%` }}
          />
        </div>
      </div>
    </div>
  )
}
