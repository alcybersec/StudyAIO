import { useMemo } from 'react'
import { useDashboard } from '../hooks/useApi'
import { LoadingSpinner, ErrorBanner, PageHeader } from '../components/ui'
import { ReviewAlert } from '../components/dashboard/ReviewAlert'
import { ActivityFeed } from '../components/dashboard/ActivityFeed'
import { CourseCard } from '../components/dashboard/CourseCard'
import { ExamCountdown } from '../components/dashboard/ExamCountdown'
import { QuickUpload } from '../components/dashboard/QuickUpload'
import { StreakDisplay } from '../components/dashboard/StreakDisplay'
import { StudyProgress } from '../components/dashboard/StudyProgress'
import { EmptyState } from '../components/ui'
import { InstallPrompt } from '../components/pwa/InstallPrompt'

export function DashboardPage() {
  const { data, isLoading, error, refetch } = useDashboard()
  const now = useMemo(() => Date.now(), []) // eslint-disable-line react-hooks/purity

  if (isLoading) return <LoadingSpinner label="Loading dashboard..." />
  if (error) return <ErrorBanner message="Failed to load dashboard. Check that the API server is running." onRetry={refetch} />

  if (!data) return null

  return (
    <div>
      <PageHeader title="Dashboard" subtitle={`${data.courses.length} course${data.courses.length !== 1 ? 's' : ''} tracked`} />

      <ReviewAlert count={data.pending_review_count} />

      {/* Streak + Exam widgets */}
      {(data.streak || (data.active_exams && data.active_exams.length > 0)) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {data.streak && <StreakDisplay streak={data.streak} />}
          {data.active_exams && data.active_exams.length > 0 && (
            <ExamCountdown exams={data.active_exams} />
          )}
        </div>
      )}

      {data.study_stats && data.study_stats.total > 0 && (
        <div className="mb-6">
          <StudyProgress stats={data.study_stats} />
        </div>
      )}

      {data.upcoming_deadlines && data.upcoming_deadlines.length > 0 && (
        <div className="mb-6 rounded-lg border border-border bg-surface p-4">
          <h3 className="mb-3 text-sm font-semibold text-text">Upcoming Deadlines</h3>
          <div className="space-y-2">
            {data.upcoming_deadlines.map((d) => {
              const days = Math.ceil(
                (new Date(d.due_date).getTime() - now) / (1000 * 60 * 60 * 24)
              )
              return (
                <div key={d.id} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex rounded bg-surface-alt px-1.5 py-0.5 text-xs font-medium text-text-muted">
                      {d.course_code}
                    </span>
                    <span className="text-text">{d.title}</span>
                    {!d.is_confirmed && (
                      <span className="text-xs text-yellow-600">(unconfirmed)</span>
                    )}
                  </div>
                  <span className={`text-xs ${days <= 3 ? 'font-medium text-red-600' : days <= 7 ? 'text-yellow-600' : 'text-text-muted'}`}>
                    {d.due_date} ({days <= 0 ? 'Today' : `${days}d`})
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2">
          <ActivityFeed items={data.recent_activity} />
        </div>
        <div>
          <QuickUpload />
        </div>
      </div>

      {data.courses.length > 0 ? (
        <section>
          <h2 className="text-sm font-semibold text-text mb-4">Your Courses</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.courses.map((course) => (
              <CourseCard key={course.id} course={course} />
            ))}
          </div>
        </section>
      ) : (
        <EmptyState
          title="No courses yet"
          description="Upload your first lecture file to get started."
          actionLabel="Upload"
          actionTo="/upload"
        />
      )}

      <InstallPrompt />
    </div>
  )
}
