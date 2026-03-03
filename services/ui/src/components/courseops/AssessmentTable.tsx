import type { Assessment } from '../../types'

interface AssessmentTableProps {
  assessments: Assessment[]
  isLoading: boolean
}

const TYPE_COLORS: Record<string, string> = {
  exam: 'bg-red-100 text-red-700',
  assignment: 'bg-blue-100 text-blue-700',
  quiz: 'bg-yellow-100 text-yellow-700',
  project: 'bg-purple-100 text-purple-700',
  lab: 'bg-green-100 text-green-700',
  presentation: 'bg-orange-100 text-orange-700',
  other: 'bg-gray-100 text-gray-700',
}

export function AssessmentTable({ assessments, isLoading }: AssessmentTableProps) {
  if (isLoading) {
    return <div className="py-8 text-center text-sm text-gray-500">Loading assessments...</div>
  }

  if (assessments.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-gray-500">
        No assessments extracted yet. Upload a course outline to get started.
      </div>
    )
  }

  const totalWeight = assessments.reduce((sum, a) => sum + (a.weight_pct ?? 0), 0)

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Assessment</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Type</th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Weight</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Weeks</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Description</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {assessments.map((a) => (
            <tr key={a.id}>
              <td className="px-4 py-3 text-sm font-medium text-gray-900">{a.title}</td>
              <td className="px-4 py-3">
                <span
                  className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                    TYPE_COLORS[a.assessment_type] ?? TYPE_COLORS.other
                  }`}
                >
                  {a.assessment_type}
                </span>
              </td>
              <td className="px-4 py-3 text-right text-sm text-gray-700">
                {a.weight_pct != null ? `${a.weight_pct}%` : '—'}
              </td>
              <td className="px-4 py-3 text-sm text-gray-500">
                {a.weeks_relevant && a.weeks_relevant.length > 0
                  ? a.weeks_relevant.join(', ')
                  : '—'}
              </td>
              <td className="max-w-xs truncate px-4 py-3 text-sm text-gray-500">
                {a.description ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
        {totalWeight > 0 && (
          <tfoot className="bg-gray-50">
            <tr>
              <td className="px-4 py-2 text-sm font-medium text-gray-900">Total</td>
              <td />
              <td className="px-4 py-2 text-right text-sm font-medium text-gray-900">{totalWeight}%</td>
              <td colSpan={2} />
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
