import { memo, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Check, RefreshCw } from 'lucide-react'
import { useDashboardCourses } from '../../hooks/useApi'
import { useRefreshTonightPlan, useTonightPlan } from '../../hooks/useWeakSpots'
import { recordUsageEvent } from '../../api/usage'
import { userErrorMessage } from '../../lib/userError'
import {
  focusWhy,
  groupPlanItems,
  planIsEmpty,
  reasonLabel,
  runnableIds,
} from '../../lib/weakSpots'
import type { PlanRunState } from '../../lib/planRun'
import { Button, Skeleton } from '../ui'
import { WidgetShell } from '../dashboard/widgets/WidgetShell'
import { selectWidgetState } from '../dashboard/widgets/widgetState'
import { PracticeBadge } from './PracticeBadge'

function TonightSkeleton() {
  return (
    <div className="space-y-2" aria-busy="true">
      <Skeleton height={14} width="60%" />
      <Skeleton height={36} width="100%" />
      <Skeleton height={36} width="100%" />
    </div>
  )
}

/** Dashboard "Study tonight" card: today's frozen plan (ADR 0007 Decision 4). */
export const TonightCard = memo(function TonightCard() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { data: plan, isLoading, isError, refetch } = useTonightPlan()
  const refresh = useRefreshTonightPlan()
  // Before any upload there is nothing to check in on, so the way forward is Upload.
  const hasMaterial = useDashboardCourses().data?.some((c) => c.total_artifacts > 0) ?? true

  // One view event each time the plan is shown with data. Fire-and-forget.
  const loaded = !!plan
  useEffect(() => {
    if (loaded) recordUsageEvent('study_plan_viewed')
  }, [loaded])

  const state = selectWidgetState({
    isLoading,
    isError,
    hasData: plan !== undefined,
    isEmpty: !!plan && planIsEmpty(plan),
  })

  const start = () => {
    if (!plan) return
    const { cardIds, quizIds } = runnableIds(plan)
    const open = plan.items.filter((i) => !i.done)
    const run: PlanRunState = {
      cardIds,
      quizIds,
      minutes: Math.max(1, open.reduce((n, i) => n + i.minutes, 0)),
      courseCodes: [...new Set(open.map((i) => i.course_code))],
    }
    navigate('/study?tab=timed', { state: { planRun: run } })
  }

  const groups = plan ? groupPlanItems(plan.items) : []
  const allDone = !!plan && plan.items.length > 0 && plan.done_count >= plan.items.length

  return (
    <WidgetShell
      title={t('Study tonight')}
      state={state}
      onRetry={() => refetch()}
      emptyIcon="🌙"
      emptyTitle={t('Nothing to practise tonight')}
      emptyHint={
        hasMaterial
          ? t("Take a short check-in or review some cards and tonight's plan will take shape.")
          : t("Upload a lecture, then take a short check-in; tonight's plan builds from your answers.")
      }
      emptyActionLabel={hasMaterial ? t('See your mastery map') : t('Upload a lecture')}
      emptyActionTo={hasMaterial ? '/study?tab=mastery' : '/upload'}
      skeleton={<TonightSkeleton />}
    >
      {plan && (
        <div className="space-y-3">
          <p className="text-xs text-text-muted" aria-live="polite">
            {t('{{count}} items · about {{minutes}} min · {{done}} done', {
              count: plan.items.length,
              minutes: plan.total_minutes,
              done: plan.done_count,
            })}
          </p>

          {plan.focus.length > 0 && (
            <div>
              <p className="text-[10px] font-mono uppercase tracking-[0.1em] text-text-faint mb-1">
                {t('Focus weeks')}
              </p>
              <ul className="space-y-1">
                {plan.focus.map((f) => (
                  <li key={`${f.course_id}:${f.week}`} className="text-xs text-text">
                    <span className="font-mono text-[10px] text-text-faint">{f.course_code}</span>{' '}
                    {t('Week {{week}}', { week: f.week })}
                    <span className="text-text-muted"> — {focusWhy(f.status, f.days_to_exam)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <ul className="divide-y divide-border">
            {groups.map((g) => (
              <li key={g.key} className="flex flex-wrap items-center gap-x-2 gap-y-1 py-1.5 text-xs">
                {g.done === g.total ? (
                  <Check size={12} className="text-sage-fg" aria-label={t('Done')} />
                ) : (
                  <span className="w-3" aria-hidden />
                )}
                <span className={g.done === g.total ? 'text-text-faint line-through' : 'text-text'}>
                  <span className="font-mono text-[10px] text-text-faint">{g.course_code}</span>{' '}
                  {t('Week {{week}}', { week: g.week })}
                </span>
                <span className="text-text-muted">
                  {t('{{cards}} cards, {{quizzes}} questions · {{minutes}} min', {
                    cards: g.cards,
                    quizzes: g.quizzes,
                    minutes: g.minutes,
                  })}
                </span>
                <span className="text-text-faint">
                  {g.reasons.map((r) => reasonLabel(r)).join(' · ')}
                </span>
                {g.targeted && <PracticeBadge />}
              </li>
            ))}
          </ul>

          {allDone && (
            <p className="text-xs text-sage-fg">{t("Everything in tonight's plan is done.")}</p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" className="min-h-[44px] md:min-h-0" onClick={start} disabled={allDone}>
              {t('Start')}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              className="min-h-[44px] md:min-h-0"
              onClick={() => refresh.mutate()}
              loading={refresh.isPending}
            >
              <RefreshCw size={12} aria-hidden /> {t('Refresh plan')}
            </Button>
          </div>

          {refresh.isError && (
            <p role="alert" className="text-xs text-red-fg">
              {userErrorMessage(refresh.error, t("Couldn't refresh the plan"))}
            </p>
          )}
        </div>
      )}
    </WidgetShell>
  )
})
