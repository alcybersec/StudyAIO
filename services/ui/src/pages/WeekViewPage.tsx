import { useParams } from 'react-router-dom'
import { useWeekDetail } from '../hooks/useApi'

export function WeekViewPage() {
  const { courseCode, weekNumber } = useParams<{ courseCode: string; weekNumber: string }>()
  const week = Number(weekNumber)
  const { data, isLoading, error } = useWeekDetail(courseCode ?? '', week)

  if (isLoading) return <p className="text-gray-500">Loading week...</p>
  if (error) return <p className="text-red-500">Failed to load week data.</p>
  if (!data) return <p className="text-gray-500">Week not found.</p>

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">
        {data.course.code} — Week {data.week}
      </h1>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Artifacts</h2>
        {data.artifacts.length === 0 ? (
          <p className="text-gray-500">No artifacts for this week.</p>
        ) : (
          <div className="bg-white rounded-lg shadow divide-y divide-gray-200">
            {data.artifacts.map((artifact) => (
              <div key={artifact.id} className="px-6 py-4 flex justify-between items-center">
                <div>
                  <p className="font-medium text-gray-900">{artifact.original_filename}</p>
                  <p className="text-sm text-gray-500">
                    {artifact.file_type.toUpperCase()} — {(artifact.file_size_bytes / 1024).toFixed(0)} KB
                  </p>
                </div>
                <span
                  className={`inline-flex px-2 py-1 text-xs rounded-full ${
                    artifact.status === 'summarized'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {artifact.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Summary</h2>
        {data.summary ? (
          <div className="bg-white rounded-lg shadow p-6 prose max-w-none">
            <p className="text-sm text-gray-500 mb-4">Version {data.summary.version}</p>
            <div className="whitespace-pre-wrap">{data.summary.content_md}</div>
          </div>
        ) : (
          <p className="text-gray-500">No summary generated yet.</p>
        )}
      </section>
    </div>
  )
}
