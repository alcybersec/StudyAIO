import { Badge } from '../ui'

export interface QueuedFile {
  id: string
  file: File
  status: 'queued' | 'uploading' | 'done' | 'error'
  artifactId?: string
  error?: string
}

interface FileQueueProps {
  files: QueuedFile[]
  onRemove: (id: string) => void
}

const statusVariant: Record<string, 'default' | 'warning' | 'success' | 'danger'> = {
  queued: 'default',
  uploading: 'warning',
  done: 'success',
  error: 'danger',
}

const statusLabel: Record<string, string> = {
  queued: 'Queued',
  uploading: 'Uploading...',
  done: 'Uploaded',
  error: 'Failed',
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

export function FileQueue({ files, onRemove }: FileQueueProps) {
  if (files.length === 0) return null

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-900">File Queue ({files.length})</h3>
      <ul className="divide-y divide-gray-100 bg-white rounded-xl border border-gray-200">
        {files.map((f) => (
          <li key={f.id} className="flex items-center gap-3 px-4 py-3">
            <span className="text-lg text-gray-400 shrink-0">
              {f.file.name.endsWith('.pdf') ? '\u{1F4C4}' : f.file.name.endsWith('.pptx') ? '\u{1F4CA}' : '\u{1F4DD}'}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{f.file.name}</p>
              <p className="text-xs text-gray-400">{formatSize(f.file.size)}</p>
              {f.error && <p className="text-xs text-red-500 mt-0.5">{f.error}</p>}
            </div>
            <Badge variant={statusVariant[f.status]}>{statusLabel[f.status]}</Badge>
            {(f.status === 'queued' || f.status === 'error') && (
              <button
                onClick={() => onRemove(f.id)}
                className="text-gray-400 hover:text-red-500 text-sm transition-colors"
                title="Remove"
              >
                {'\u2717'}
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
