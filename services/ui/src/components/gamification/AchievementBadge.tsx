import type { LucideIcon } from 'lucide-react'
import {
  Book,
  Brain,
  Check,
  Crown,
  Flame,
  Folder,
  Medal,
  Play,
  Star,
  Target,
  Trophy,
  Upload,
  Zap,
} from 'lucide-react'
import { Tooltip } from '../ui'
import type { Achievement } from '../../types'

interface AchievementBadgeProps {
  achievement: Achievement
}

const iconMap: Record<string, LucideIcon> = {
  star: Star,
  upload: Upload,
  folder: Folder,
  play: Play,
  book: Book,
  trophy: Trophy,
  crown: Crown,
  check: Check,
  medal: Medal,
  flame: Flame,
  zap: Zap,
  target: Target,
  brain: Brain,
}

export function AchievementBadge({ achievement }: AchievementBadgeProps) {
  const Icon = iconMap[achievement.icon] ?? Star

  return (
    <Tooltip content={achievement.description}>
      <div
        className={`flex flex-col items-center gap-1.5 rounded-xl border p-3 text-center transition-colors ${
          achievement.earned ? 'border-peri/30 bg-peri-soft' : 'border-border bg-surface-1 opacity-60'
        }`}
      >
        <Icon size={20} aria-hidden className={achievement.earned ? 'text-peri-fg' : 'text-text-faint'} />
        <span className="text-xs font-medium text-text leading-tight">{achievement.title}</span>
        {achievement.xp_reward > 0 && (
          <span className="text-[10px] font-mono text-text-faint">+{achievement.xp_reward} XP</span>
        )}
      </div>
    </Tooltip>
  )
}
