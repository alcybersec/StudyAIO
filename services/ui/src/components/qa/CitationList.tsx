import { Link } from 'react-router-dom'
import type { Citation } from '../../types'

interface CitationListProps {
  citations: Citation[]
}

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) return null

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
        Referenced Sources
      </h4>
      <div className="space-y-2">
        {citations.map((c) => (
          <div
            key={c.ref}
            className="flex items-start gap-3 p-2 bg-white rounded border border-gray-100"
          >
            <span className="text-xs font-bold text-primary bg-primary/10 rounded-full w-6 h-6 flex items-center justify-center shrink-0">
              {c.ref}
            </span>
            <div className="min-w-0 flex-1">
              <Link
                to={`/courses/${c.course_code}/weeks/${c.week}`}
                className="text-sm font-medium text-gray-900 hover:text-primary transition-colors"
              >
                {c.course_code} — Week {c.week}
              </Link>
              <p className="text-xs text-gray-500 mt-0.5">
                Page {c.page_ref}
              </p>
              {c.text_snippet && (
                <p className="text-xs text-gray-400 mt-1 italic line-clamp-1">
                  {c.text_snippet}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
