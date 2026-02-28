import { useState } from 'react'

interface CustomResolutionFormProps {
  onSubmit: (resolution: Record<string, unknown>) => void
  isLoading: boolean
}

export function CustomResolutionForm({ onSubmit, isLoading }: CustomResolutionFormProps) {
  const [courseCode, setCourseCode] = useState('')
  const [weekNumber, setWeekNumber] = useState('')
  const [title, setTitle] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const resolution: Record<string, unknown> = {}
    if (courseCode.trim()) resolution.course_code = courseCode.trim()
    if (weekNumber.trim()) resolution.week = Number(weekNumber)
    if (title.trim()) resolution.title = title.trim()
    if (Object.keys(resolution).length > 0) {
      onSubmit(resolution)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Manual Override</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label htmlFor="course-code" className="block text-xs text-gray-500 mb-1">Course Code</label>
          <input
            id="course-code"
            type="text"
            value={courseCode}
            onChange={(e) => setCourseCode(e.target.value)}
            placeholder="e.g. CSIT302"
            className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
        </div>
        <div>
          <label htmlFor="week-num" className="block text-xs text-gray-500 mb-1">Week Number</label>
          <input
            id="week-num"
            type="number"
            min={1}
            max={52}
            value={weekNumber}
            onChange={(e) => setWeekNumber(e.target.value)}
            placeholder="e.g. 3"
            className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
        </div>
        <div>
          <label htmlFor="title" className="block text-xs text-gray-500 mb-1">Title</label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Data Structures"
            className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
        </div>
      </div>
      <button
        type="submit"
        disabled={isLoading || (!courseCode.trim() && !weekNumber.trim() && !title.trim())}
        className="px-4 py-2.5 text-sm font-medium bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? 'Resolving...' : 'Resolve with these values'}
      </button>
    </form>
  )
}
