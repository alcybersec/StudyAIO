import { Link, useParams } from 'react-router-dom'
import { useCourseDetail } from '../hooks/useApi'

export function CoursePage() {
  const { courseCode } = useParams<{ courseCode: string }>()
  const { data, isLoading, error } = useCourseDetail(courseCode ?? '')

  if (isLoading) return <p className="text-gray-500">Loading course...</p>
  if (error) return <p className="text-red-500">Failed to load course.</p>
  if (!data) return <p className="text-gray-500">Course not found.</p>

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">{data.course.code}</h1>
      {data.course.name && <p className="text-gray-500 mb-6">{data.course.name}</p>}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Week</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Files</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Summary</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Flashcards</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Quizzes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {data.weeks.map((week) => (
              <tr key={week.week} className="hover:bg-gray-50">
                <td className="px-6 py-4">
                  <Link
                    to={`/courses/${courseCode}/weeks/${week.week}`}
                    className="text-primary font-medium hover:underline"
                  >
                    Week {week.week}
                  </Link>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">{week.artifact_count}</td>
                <td className="px-6 py-4">
                  <span
                    className={`inline-flex px-2 py-1 text-xs rounded-full ${
                      week.summary_status === 'generated'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-yellow-100 text-yellow-800'
                    }`}
                  >
                    {week.summary_status}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">{week.flashcard_count}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{week.quiz_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
