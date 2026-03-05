interface XPBarProps {
  level: number
  totalXP: number
  progressPct: number
  nextThreshold: number | null
}

export function XPBar({ level, totalXP, progressPct, nextThreshold }: XPBarProps) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 font-bold text-sm">
        {level}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="font-medium text-text">Level {level}</span>
          <span className="text-text-muted">
            {totalXP} XP{nextThreshold !== null && ` / ${nextThreshold}`}
          </span>
        </div>
        <div className="h-2 w-full rounded-full bg-surface-alt overflow-hidden">
          <div
            className="h-full rounded-full bg-indigo-500 transition-all duration-500 ease-out"
            style={{ width: `${Math.min(progressPct, 100)}%` }}
          />
        </div>
      </div>
    </div>
  )
}
