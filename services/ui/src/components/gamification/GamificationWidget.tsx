import type { DashboardGamificationSummary } from '../../types'
import { XPBar } from './XPBar'
import { DailyChallenges } from './DailyChallenges'

interface GamificationWidgetProps {
  gamification: DashboardGamificationSummary
}

export function GamificationWidget({ gamification }: GamificationWidgetProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-surface p-4">
        <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-1.5">
          <span>{'\u26A1'}</span> Your Progress
        </h3>
        <XPBar
          level={gamification.level}
          totalXP={gamification.total_xp}
          progressPct={gamification.progress_pct}
          nextThreshold={gamification.next_threshold}
        />
      </div>
      <DailyChallenges challenge={gamification} />
    </div>
  )
}
