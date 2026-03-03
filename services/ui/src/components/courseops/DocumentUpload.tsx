import { useState, useCallback } from 'react'
import { useUploadCourseDocument } from '../../hooks/useApi'

interface DocumentUploadProps {
  courseCode: string
}

const DOCUMENT_TYPES = [
  { value: 'outline', label: 'Course Outline' },
  { value: 'rubric', label: 'Rubric' },
  { value: 'handbook', label: 'Handbook' },
  { value: 'other', label: 'Other' },
]

export function DocumentUpload({ courseCode }: DocumentUploadProps) {
  const [documentType, setDocumentType] = useState('outline')
  const [dragOver, setDragOver] = useState(false)
  const upload = useUploadCourseDocument()

  const handleFile = useCallback(
    (file: File) => {
      upload.mutate({ file, courseCode, documentType })
    },
    [upload, courseCode, documentType]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-gray-700">Document type:</label>
        <select
          value={documentType}
          onChange={(e) => setDocumentType(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          {DOCUMENT_TYPES.map((dt) => (
            <option key={dt.value} value={dt.value}>
              {dt.label}
            </option>
          ))}
        </select>
      </div>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
          dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
        }`}
      >
        <svg className="mb-3 h-10 w-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-sm text-gray-600">
          Drop a course document here, or{' '}
          <label className="cursor-pointer text-blue-600 hover:underline">
            browse
            <input type="file" className="hidden" accept=".pdf,.docx,.pptx" onChange={handleChange} />
          </label>
        </p>
        <p className="mt-1 text-xs text-gray-400">PDF, DOCX, or PPTX</p>
      </div>

      {upload.isPending && (
        <div className="flex items-center gap-2 text-sm text-blue-600">
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Uploading and processing...
        </div>
      )}

      {upload.isError && (
        <p className="text-sm text-red-600">
          {upload.error instanceof Error ? upload.error.message : 'Upload failed'}
        </p>
      )}

      {upload.isSuccess && (
        <p className="text-sm text-green-600">
          Document uploaded. AI extraction in progress...
        </p>
      )}
    </div>
  )
}
