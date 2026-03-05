import { useEffect } from 'react'
import { useUnnotifiedAchievements, useMarkAchievementsNotified } from '../../hooks/useApi'

export function AchievementUnlock() {
  const { data: unnotified } = useUnnotifiedAchievements()
  const markNotified = useMarkAchievementsNotified()

  useEffect(() => {
    if (!unnotified || unnotified.length === 0) return

    // Auto-dismiss after 5 seconds
    const timer = setTimeout(() => {
      const ids = unnotified.map((a) => a.user_achievement_id)
      markNotified.mutate(ids)
    }, 5000)

    return () => clearTimeout(timer)
  }, [unnotified]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!unnotified || unnotified.length === 0) return null

  const achievement = unnotified[0]

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-4 fade-in duration-300">
      <div className="flex items-center gap-3 rounded-lg border border-indigo-200 dark:border-indigo-800 bg-surface p-4 shadow-lg">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-xl">
          {'\uD83C\uDFC6'}
        </div>
        <div>
          <p className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">
            Achievement Unlocked!
          </p>
          <p className="text-sm font-medium text-text">{achievement.title}</p>
          {achievement.xp_reward > 0 && (
            <p className="text-xs text-text-muted">+{achievement.xp_reward} XP</p>
          )}
        </div>
        <button
          onClick={() => markNotified.mutate([achievement.user_achievement_id])}
          className="ml-2 text-text-muted hover:text-text"
          aria-label="Dismiss"
        >
          &times;
        </button>
      </div>
    </div>
  )
}
