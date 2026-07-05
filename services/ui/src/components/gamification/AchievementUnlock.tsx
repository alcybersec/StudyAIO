import { useEffect } from 'react'
import { motion } from 'motion/react'
import { Trophy, X } from 'lucide-react'
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
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="fixed bottom-6 right-6 z-50"
      role="status"
    >
      <div className="flex items-center gap-3 rounded-xl border border-peri/30 bg-surface-1 p-4 shadow-lg shadow-black/10">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-peri-soft text-peri-fg">
          <Trophy size={18} aria-hidden />
        </div>
        <div>
          <p className="text-[10px] font-mono font-medium uppercase tracking-[0.12em] text-peri-fg">
            Achievement unlocked
          </p>
          <p className="text-sm font-medium text-text">{achievement.title}</p>
          {achievement.xp_reward > 0 && (
            <p className="text-xs font-mono text-text-faint">+{achievement.xp_reward} XP</p>
          )}
        </div>
        <button
          onClick={() => markNotified.mutate([achievement.user_achievement_id])}
          className="ml-2 text-text-muted hover:text-text transition-colors"
          aria-label="Dismiss"
        >
          <X size={14} aria-hidden />
        </button>
      </div>
    </motion.div>
  )
}
