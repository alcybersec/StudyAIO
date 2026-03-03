import { useState } from 'react'
import { useCourses, useCreateExam } from '../../hooks/useApi'

interface ExamCreateFormProps {
  onClose: () => void
  onCreated?: () => void
}

export function ExamCreateForm({ onClose, onCreated }: ExamCreateFormProps) {
  const { data: courses } = useCourses()
  const createExam = useCreateExam()

  const [courseCode, setCourseCode] = useState('')
  const [title, setTitle] = useState('')
  const [examDate, setExamDate] = useState('')
  const [weeksInput, setWeeksInput] = useState('')
  const [targetMastery, setTargetMastery] = useState(80)

  const parsedWeeks = weeksInput
    .split(',')
    .map((s) => parseInt(s.trim(), 10))
    .filter((n) => !isNaN(n) && n > 0)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!courseCode || !title || !examDate || parsedWeeks.length === 0) return

    await createExam.mutateAsync({
      course_code: courseCode,
      title,
      exam_date: new Date(examDate).toISOString(),
      weeks_scope: parsedWeeks,
      target_mastery_pct: targetMastery,
    })

    onCreated?.()
    onClose()
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Create Exam</h3>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        >
          {'\u2715'}
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Course</label>
          <select
            value={courseCode}
            onChange={(e) => setCourseCode(e.target.value)}
            className="w-full p-2.5 min-h-[44px] rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            required
          >
            <option value="">Select a course</option>
            {courses?.map((c) => (
              <option key={c.id} value={c.code}>
                {c.code} {c.name ? `- ${c.name}` : ''}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Exam Title</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Midterm Exam"
            className="w-full p-2.5 min-h-[44px] rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Exam Date</label>
          <input
            type="datetime-local"
            value={examDate}
            onChange={(e) => setExamDate(e.target.value)}
            className="w-full p-2.5 min-h-[44px] rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Weeks Covered <span className="text-gray-400 font-normal">(comma-separated)</span>
          </label>
          <input
            type="text"
            value={weeksInput}
            onChange={(e) => setWeeksInput(e.target.value)}
            placeholder="e.g., 1, 2, 3, 4, 5"
            className="w-full p-2.5 min-h-[44px] rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            required
          />
          {parsedWeeks.length > 0 && (
            <div className="flex gap-1.5 mt-2 flex-wrap">
              {parsedWeeks.map((w) => (
                <span key={w} className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium">
                  W{w}
                </span>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Target Mastery: {targetMastery}%
          </label>
          <input
            type="range"
            min={50}
            max={100}
            step={5}
            value={targetMastery}
            onChange={(e) => setTargetMastery(Number(e.target.value))}
            className="w-full"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={createExam.isPending || !courseCode || !title || !examDate || parsedWeeks.length === 0}
            className="flex-1 px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-primary text-white hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {createExam.isPending ? 'Creating...' : 'Create Exam'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
          >
            Cancel
          </button>
        </div>

        {createExam.isError && (
          <div className="p-3 rounded-lg bg-red-50 text-sm text-red-700">
            {(createExam.error as Error).message || 'Failed to create exam'}
          </div>
        )}
      </form>
    </div>
  )
}
