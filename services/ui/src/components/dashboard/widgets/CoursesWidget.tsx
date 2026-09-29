import { memo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useDashboardCourses } from '../../../hooks/useApi'
import { Skeleton } from '../../ui'
import { WidgetShell } from './WidgetShell'
import { selectWidgetState } from './widgetState'

function CoursesSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5">
      {[0, 1, 2].map((i) => (
        <div key={i} className="bg-surface-2 rounded-lg p-3 space-y-2">
          <Skeleton height={14} width="55%" />
          <Skeleton height={11} width="85%" />
          <Skeleton height={10} width="65%" />
        </div>
      ))}
    </div>
  )
}

export const CoursesWidget = memo(function CoursesWidget() {
  const { t } = useTranslation()

  const { data, isLoading, isError, refetch } = useDashboardCourses()
  const state = selectWidgetState({
    isLoading,
    isError,
    hasData: data !== undefined,
    isEmpty: !data || data.length === 0,
  })

  return (
    <WidgetShell
      title={t('Courses')}
      state={state}
      onRetry={() => refetch()}
      emptyTitle={t('No courses yet')}
      emptyHint={t('Upload your first lecture and a course is created automatically.')}
      emptyActionLabel={t('Upload')}
      emptyActionTo="/upload"
      skeleton={<CoursesSkeleton />}
    >
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5">
        {data?.map((course) => (
          <Link
            key={course.id}
            to={`/courses/${course.code}`}
            className="bg-surface-2 hover:bg-surface-0 border border-transparent hover:border-border rounded-lg p-3 text-left transition-colors"
          >
            <div className="text-[13px] font-semibold text-text">{course.code}</div>
            <div className="text-[11px] text-text-muted truncate">{course.name ?? '—'}</div>
            <div className="text-[10px] text-text-faint font-mono mt-1.5">
              {t('{{weeks}} wks · {{files}} files', {
                weeks: course.weeks_covered,
                files: course.total_artifacts,
              })}
            </div>
          </Link>
        ))}
      </div>
    </WidgetShell>
  )
})
