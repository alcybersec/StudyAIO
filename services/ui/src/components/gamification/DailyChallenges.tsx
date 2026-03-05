import type { DashboardGamificationSummary } from '../../types'

interface DailyChallengesProps {
  challenge: DashboardGamificationSummary
}

export function DailyChallenges({ challenge }: DailyChallengesProps) {
  const progressPct =
    challenge.daily_challenge_target > 0
      ? Math.min(
          (challenge.daily_challenge_progress / challenge.daily_challenge_target) * 100,
          100
        )
      : 0

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-text flex items-center gap-1.5">
          <span>{'\uD83C\uDFAF'}</span> Daily Challenge
        </h3>
        {challenge.daily_challenge_completed && (
          <span className="text-xs font-medium text-green-600 dark:text-green-400">
            {'\u2705'} Complete
          </span>
        )}
      </div>
      {challenge.daily_challenge_description && (
        <>
          <p className="text-sm text-text-muted mb-2">
            {challenge.daily_challenge_description}
          </p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 rounded-full bg-surface-alt overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  challenge.daily_challenge_completed
                    ? 'bg-green-500'
                    : 'bg-amber-500'
                }`}
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-xs text-text-muted whitespace-nowrap">
              {challenge.daily_challenge_progress}/{challenge.daily_challenge_target}
            </span>
          </div>
        </>
      )}
    </div>
  )
}
