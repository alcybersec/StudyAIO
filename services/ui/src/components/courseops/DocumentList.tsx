import { EmptyState, ErrorState, Skeleton, StatusBadge } from '../ui'
import type { CourseDocument } from '../../types'

interface DocumentListProps {
  documents: CourseDocument[] | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function DocumentListSkeleton() {
  return (
    <div className="mt-4 divide-y divide-border rounded-xl border border-border" role="status" aria-label="Loading documents">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="flex items-center justify-between px-4 py-3">
          <div className="flex-1 space-y-2">
            <Skeleton height={14} width="50%" />
            <Skeleton height={10} width="35%" />
          </div>
          <Skeleton height={18} width={72} rounded />
        </div>
      ))}
    </div>
  )
}

export function DocumentList({ documents, isLoading, isError, onRetry }: DocumentListProps) {
  if (isLoading && !documents) return <DocumentListSkeleton />

  if (isError && !documents) {
    return (
      <div className="mt-4">
        <ErrorState compact title="Documents couldn't load" onRetry={onRetry} />
      </div>
    )
  }

  if (!documents || documents.length === 0) {
    return (
      <div className="mt-4 rounded-xl border border-border">
        <EmptyState
          compact
          title="No documents uploaded yet"
          description="Upload a course outline above to extract assessments and deadlines."
        />
      </div>
    )
  }

  return (
    <div className="mt-4 divide-y divide-border rounded-xl border border-border">
      {documents.map((doc) => (
        <div key={doc.id} className="flex items-center justify-between px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-text">{doc.original_filename}</p>
            <p className="text-xs text-text-muted font-mono">
              {doc.document_type} &middot; {formatBytes(doc.file_size_bytes)} &middot;{' '}
              {new Date(doc.created_at).toLocaleDateString()}
            </p>
          </div>
          <span className="ml-3 shrink-0">
            <StatusBadge status={doc.status} />
          </span>
        </div>
      ))}
    </div>
  )
}
