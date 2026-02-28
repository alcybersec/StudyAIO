import { useState } from 'react'
import type { CourseListItem } from '../../types'

interface QuestionFormProps {
  courses: CourseListItem[]
  onSubmit: (question: string, courseCode?: string, week?: number) => void
  isLoading: boolean
  defaultCourseCode?: string
  defaultWeek?: number
}

export function QuestionForm({
  courses,
  onSubmit,
  isLoading,
  defaultCourseCode,
  defaultWeek,
}: QuestionFormProps) {
  const [question, setQuestion] = useState('')
  const [courseCode, setCourseCode] = useState(defaultCourseCode ?? '')
  const [week, setWeek] = useState<string>(defaultWeek?.toString() ?? '')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || isLoading) return
    onSubmit(
      question.trim(),
      courseCode || undefined,
      week ? Number(week) : undefined,
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about your lectures..."
          rows={3}
          className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary resize-none"
          disabled={isLoading}
        />
      </div>

      <div className="flex flex-wrap items-end gap-3">
        {/* Scope filters — only show if not pre-scoped */}
        {defaultCourseCode === undefined && (
          <>
            <div className="flex-1 min-w-[140px]">
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Course (optional)
              </label>
              <select
                value={courseCode}
                onChange={(e) => {
                  setCourseCode(e.target.value)
                  if (!e.target.value) setWeek('')
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                disabled={isLoading}
              >
                <option value="">All courses</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.code}>
                    {c.code}
                  </option>
                ))}
              </select>
            </div>

            {courseCode && (
              <div className="w-24">
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Week
                </label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={week}
                  onChange={(e) => setWeek(e.target.value)}
                  placeholder="All"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  disabled={isLoading}
                />
              </div>
            )}
          </>
        )}

        <button
          type="submit"
          disabled={!question.trim() || isLoading}
          className="px-5 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? 'Thinking...' : 'Ask'}
        </button>
      </div>
    </form>
  )
}
