import { usePendingReviews } from '../hooks/useApi'

export function ReviewInboxPage() {
  const { data, isLoading, error } = usePendingReviews()

  if (isLoading) return <p className="text-gray-500">Loading review items...</p>
  if (error) return <p className="text-red-500">Failed to load review items.</p>

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Review Inbox</h1>

      {data && data.length === 0 && (
        <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
          No pending review items. All caught up!
        </div>
      )}

      {data && data.length > 0 && (
        <div className="space-y-4">
          {data.map((item) => (
            <div key={item.id} className="bg-white rounded-lg shadow p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <span className="inline-flex px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-800">
                    {item.review_type}
                  </span>
                  <p className="mt-2 text-sm text-gray-500">
                    Entity: {item.entity_type} / {item.entity_id}
                  </p>
                </div>
                <p className="text-xs text-gray-400">{new Date(item.created_at).toLocaleDateString()}</p>
              </div>
              <div className="text-sm text-gray-700">
                <p className="font-medium mb-1">Suggested values:</p>
                <pre className="bg-gray-50 p-2 rounded text-xs overflow-auto">
                  {JSON.stringify(item.suggested_values, null, 2)}
                </pre>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
