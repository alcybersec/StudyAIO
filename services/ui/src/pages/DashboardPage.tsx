import { Link } from 'react-router-dom'
import { useDashboard } from '../hooks/useApi'

export function DashboardPage() {
  const { data, isLoading, error } = useDashboard()

  if (isLoading) return <p className="text-gray-500">Loading dashboard...</p>
  if (error) return <p className="text-red-500">Failed to load dashboard.</p>

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-500">Courses</p>
            <p className="text-3xl font-bold text-gray-900">{data.courses.length}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-500">Pending Reviews</p>
            <p className="text-3xl font-bold text-gray-900">{data.pending_review_count}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-500">Recent Activity</p>
            <p className="text-3xl font-bold text-gray-900">{data.recent_activity.length}</p>
          </div>
        </div>
      )}

      {data?.courses && data.courses.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Courses</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.courses.map((course) => (
              <Link
                key={course.id}
                to={`/courses/${course.code}`}
                className="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow"
              >
                <h3 className="text-lg font-bold text-gray-900">{course.code}</h3>
                {course.name && <p className="text-sm text-gray-500">{course.name}</p>}
                <div className="mt-4 flex gap-4 text-sm text-gray-500">
                  <span>{course.weeks_covered} weeks</span>
                  <span>{course.total_artifacts} files</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
