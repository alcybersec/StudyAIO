import type { StreakInfo } from '../../types'

interface StreakDisplayProps {
  streak: StreakInfo
}

export function StreakDisplay({ streak }: StreakDisplayProps) {
  if (streak.current_streak === 0 && streak.longest_streak === 0) return null

  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <div className="flex items-center gap-3">
        <div className="text-2xl">
          {streak.current_streak > 0 ? '\u{1F525}' : '\u{1F9CA}'}
        </div>
        <div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-text">
              {streak.current_streak}
            </span>
            <span className="text-sm text-text-muted">day streak</span>
          </div>
          {streak.longest_streak > streak.current_streak && (
            <div className="text-xs text-text-muted">
              Best: {streak.longest_streak} days
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
