import { useState } from 'react'
import { useUpdateDeadline } from '../../hooks/useApi'
import type { Deadline } from '../../types'

interface DeadlineEditModalProps {
  deadline: Deadline
  onClose: () => void
}

export function DeadlineEditModal({ deadline, onClose }: DeadlineEditModalProps) {
  const [title, setTitle] = useState(deadline.title)
  const [dueDate, setDueDate] = useState(deadline.due_date)
  const [deadlineType, setDeadlineType] = useState(deadline.deadline_type)
  const [description, setDescription] = useState(deadline.description ?? '')
  const updateDeadline = useUpdateDeadline()

  const handleSave = () => {
    updateDeadline.mutate(
      {
        deadlineId: deadline.id,
        data: {
          title,
          due_date: dueDate,
          deadline_type: deadlineType,
          description: description || undefined,
          is_confirmed: true,
        },
      },
      { onSuccess: onClose }
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="mx-4 w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-4 text-lg font-medium text-gray-900">Edit Deadline</h3>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Due Date</label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Type</label>
            <select
              value={deadlineType}
              onChange={(e) => setDeadlineType(e.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {['exam', 'assignment', 'quiz', 'project', 'lab', 'presentation', 'other'].map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={updateDeadline.isPending || !title.trim() || !dueDate}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {updateDeadline.isPending ? 'Saving...' : 'Save & Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}
