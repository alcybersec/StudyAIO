import { useDashboard } from '../hooks/useApi'
import { LoadingSpinner, EmptyState, PageHeader } from '../components/ui'
import { ReviewAlert } from '../components/dashboard/ReviewAlert'
import { ActivityFeed } from '../components/dashboard/ActivityFeed'
import { CourseCard } from '../components/dashboard/CourseCard'
import { QuickUpload } from '../components/dashboard/QuickUpload'

export function DashboardPage() {
  const { data, isLoading, error } = useDashboard()

  if (isLoading) return <LoadingSpinner label="Loading dashboard..." />
  if (error) return <EmptyState icon="!" title="Failed to load dashboard" description="Check that the API server is running." />

  if (!data) return null

  return (
    <div>
      <PageHeader title="Dashboard" subtitle={`${data.courses.length} course${data.courses.length !== 1 ? 's' : ''} tracked`} />

      <ReviewAlert count={data.pending_review_count} />

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
