import type { Achievement } from '../../types'

interface AchievementBadgeProps {
  achievement: Achievement
}

const iconMap: Record<string, string> = {
  star: '\u2B50',
  upload: '\uD83D\uDCE4',
  folder: '\uD83D\uDCC1',
  play: '\u25B6\uFE0F',
  book: '\uD83D\uDCD6',
  trophy: '\uD83C\uDFC6',
  crown: '\uD83D\uDC51',
  check: '\u2705',
  medal: '\uD83C\uDFC5',
  flame: '\uD83D\uDD25',
  zap: '\u26A1',
  target: '\uD83C\uDFAF',
  brain: '\uD83E\uDDE0',
}

export function AchievementBadge({ achievement }: AchievementBadgeProps) {
  const icon = iconMap[achievement.icon] || '\u2B50'

  return (
    <div
      className={`group relative flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center transition-colors ${
        achievement.earned
          ? 'border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-900/20'
          : 'border-border bg-surface opacity-50 grayscale'
      }`}
    >
      <span className="text-2xl">{icon}</span>
      <span className="text-xs font-medium text-text leading-tight">{achievement.title}</span>
      {achievement.xp_reward > 0 && (
        <span className="text-[10px] text-text-muted">+{achievement.xp_reward} XP</span>
      )}

      {/* Tooltip */}
      <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 whitespace-nowrap rounded bg-gray-900 dark:bg-gray-100 px-2 py-1 text-xs text-white dark:text-gray-900 opacity-0 transition-opacity group-hover:opacity-100">
        {achievement.description}
      </div>
    </div>
  )
}
