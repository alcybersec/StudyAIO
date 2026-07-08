import { useState, useCallback } from 'react'
import { FilePlus, Loader2 } from 'lucide-react'
import { useUploadCourseDocument } from '../../hooks/useApi'
import { Select } from '../ui'

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
    [upload, courseCode, documentType],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-text-muted">Document type:</label>
        <Select className="w-44" options={DOCUMENT_TYPES} value={documentType} onValueChange={setDocumentType} />
      </div>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-colors ${
          dragOver ? 'border-peri bg-peri-soft/40' : 'border-border hover:border-border-strong'
        }`}
      >
        <FilePlus size={32} aria-hidden className="mb-3 text-text-faint" />
        <p className="text-sm text-text-muted">
          Drop a course document here, or{' '}
          <label className="cursor-pointer text-peri-fg hover:underline">
            browse
            <input type="file" className="hidden" accept=".pdf,.docx,.pptx" onChange={handleChange} />
          </label>
        </p>
        <p className="mt-1 text-xs text-text-faint font-mono">PDF, DOCX, or PPTX</p>
      </div>

      {upload.isPending && (
        <div className="flex items-center gap-2 text-sm text-text-muted" role="status">
          <Loader2 size={14} aria-hidden className="animate-spin" />
          Uploading and processing...
        </div>
      )}

      {upload.isError && (
        <p className="text-sm text-red-fg" role="alert">
          {upload.error instanceof Error ? upload.error.message : 'Upload failed'}
        </p>
      )}

      {upload.isSuccess && <p className="text-sm text-sage-fg">Document uploaded. AI extraction in progress...</p>}
    </div>
  )
}
