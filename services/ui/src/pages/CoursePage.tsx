import { Link, useParams } from 'react-router-dom'
import { useCourseDetail } from '../hooks/useApi'
import { LoadingSpinner, EmptyState, ErrorBanner, PageHeader, Card } from '../components/ui'
import { WeekRow } from '../components/course/WeekRow'
import { ExportButton } from '../components/course/ExportButton'

export function CoursePage() {
  const { courseCode } = useParams<{ courseCode: string }>()
  const { data, isLoading, error, refetch } = useCourseDetail(courseCode ?? '')

  if (isLoading) return <LoadingSpinner label="Loading course..." />
  if (error) return <ErrorBanner message="Failed to load course. Check that the course exists." onRetry={refetch} />
  if (!data) return <EmptyState icon="?" title="Course not found" />

  return (
    <div>
      <PageHeader
        title={data.course.code}
        subtitle={data.course.name ?? undefined}
        breadcrumbs={[
          { label: 'Dashboard', to: '/' },
          { label: data.course.code },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Link
              to={`/courses/${courseCode}/ops`}
              className="inline-flex items-center px-4 py-2 border border-border text-text text-sm font-medium rounded-lg hover:bg-surface-alt transition-colors"
            >
              Course Docs
            </Link>
            <ExportButton courseCode={courseCode!} />
            <Link
              to="/upload"
              className="inline-flex items-center px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors"
            >
              Upload files
            </Link>
          </div>
        }
      />

      {data.weeks.length === 0 ? (
        <EmptyState
          title="No weeks yet"
          description="Upload lecture files for this course to populate weeks."
          actionLabel="Upload"
          actionTo="/upload"
        />
      ) : (
        <Card padding={false}>
          <ul className="divide-y divide-border">
            {data.weeks.map((week) => (
              <li key={week.week}>
                <WeekRow courseCode={courseCode!} week={week} />
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
