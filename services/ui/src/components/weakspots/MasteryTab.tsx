import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useWeakSpots } from '../../hooks/useWeakSpots'
import { useOnlineStatus } from '../../hooks/useOnlineStatus'
import { Card, EmptyState, ErrorState, Skeleton } from '../ui'
import { MasteryHeatmap, MasteryLegend, type HeatmapSelection } from './MasteryHeatmap'
import { WeekPanel } from './WeekPanel'

function MasterySkeleton() {
  return (
    <Card aria-busy="true">
      <div className="space-y-3">
        {[0, 1].map((r) => (
          <div key={r} className="flex flex-wrap gap-1.5">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} width={44} height={44} />
            ))}
          </div>
        ))}
      </div>
    </Card>
  )
}

/** Study hub tab: the course x week mastery map plus the selected week's panel. */
export function MasteryTab() {
  const { t } = useTranslation()
  const { data, isLoading, error, refetch } = useWeakSpots()
  const online = useOnlineStatus()
  const [selected, setSelected] = useState<HeatmapSelection | null>(null)

  if (error && !data) {
    return (
      <ErrorState
        title={online ? t("The mastery map couldn't load") : t("You're offline")}
        onRetry={() => refetch()}
      />
    )
  }
  if (isLoading || !data) return <MasterySkeleton />

  const courses = data.courses.filter((c) => c.weeks.length > 0)
  if (courses.length === 0) {
    return (
      <EmptyState
        title={t('No weeks to map yet')}
        description={t('Upload lectures and study a little; each week shows up here once it has material.')}
        actionLabel={t('Upload lectures')}
        actionTo="/upload"
      />
    )
  }

  const course = courses.find((c) => c.course_id === selected?.courseId)
  const week = course?.weeks.find((w) => w.week === selected?.week)

  return (
    <div className="max-w-3xl space-y-4">
      <Card>
        <div className="space-y-4">
          <MasteryLegend />
          <MasteryHeatmap courses={courses} selected={selected} onSelect={setSelected} />
          <p className="text-xs text-text-faint">
            {t('Grey means not enough data yet, not a problem. Select a week for details.')}
          </p>
        </div>
      </Card>
      {course && week && <WeekPanel key={`${course.course_id}:${week.week}`} course={course} week={week} />}
    </div>
  )
}
