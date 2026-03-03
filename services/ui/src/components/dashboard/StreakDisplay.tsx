import type { StreakInfo } from '../../types'

interface StreakDisplayProps {
  streak: StreakInfo
}

export function StreakDisplay({ streak }: StreakDisplayProps) {
  if (streak.current_streak === 0 && streak.longest_streak === 0) return null

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <div className="flex items-center gap-3">
        <div className="text-2xl">
          {streak.current_streak > 0 ? '\u{1F525}' : '\u{1F9CA}'}
        </div>
        <div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-gray-900">
              {streak.current_streak}
            </span>
            <span className="text-sm text-gray-500">day streak</span>
          </div>
          {streak.longest_streak > streak.current_streak && (
            <div className="text-xs text-gray-400">
              Best: {streak.longest_streak} days
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
