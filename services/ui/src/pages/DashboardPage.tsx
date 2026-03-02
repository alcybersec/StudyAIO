import { useDashboard } from '../hooks/useApi'
import { LoadingSpinner, ErrorBanner, PageHeader } from '../components/ui'
import { ReviewAlert } from '../components/dashboard/ReviewAlert'
import { ActivityFeed } from '../components/dashboard/ActivityFeed'
import { CourseCard } from '../components/dashboard/CourseCard'
import { QuickUpload } from '../components/dashboard/QuickUpload'
import { StudyProgress } from '../components/dashboard/StudyProgress'
import { EmptyState } from '../components/ui'

export function DashboardPage() {
  const { data, isLoading, error, refetch } = useDashboard()

  if (isLoading) return <LoadingSpinner label="Loading dashboard..." />
  if (error) return <ErrorBanner message="Failed to load dashboard. Check that the API server is running." onRetry={refetch} />

  if (!data) return null

  return (
    <div>
      <PageHeader title="Dashboard" subtitle={`${data.courses.length} course${data.courses.length !== 1 ? 's' : ''} tracked`} />

      <ReviewAlert count={data.pending_review_count} />

      {data.study_stats && data.study_stats.total > 0 && (
        <div className="mb-6">
          <StudyProgress stats={data.study_stats} />
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
          <h2 className="text-sm font-semibold text-gray-900 mb-4">Your Courses</h2>
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
    </div>
  )
}
