import { useState } from 'react'
import { Badge, StatusBadge } from '../ui'
import type { Artifact } from '../../types'

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

const typeVariant: Record<string, 'info' | 'success' | 'warning' | 'default'> = {
  pdf: 'danger' as 'info',
  docx: 'info',
  pptx: 'warning',
}

interface ArtifactListProps {
  artifacts: Artifact[]
}

export function ArtifactList({ artifacts }: ArtifactListProps) {
  const [expanded, setExpanded] = useState(true)

  if (artifacts.length === 0) {
    return <p className="text-sm text-gray-500 py-4">No source artifacts for this week.</p>
  }

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-semibold text-gray-700 hover:text-gray-900 mb-3 transition-colors"
      >
        <span className="text-xs">{expanded ? '\u25BC' : '\u25B6'}</span>
        Source Files ({artifacts.length})
      </button>
      {expanded && (
        <ul className="divide-y divide-gray-100 bg-white rounded-xl border border-gray-200">
          {artifacts.map((artifact) => (
            <li key={artifact.id} className="flex items-center gap-3 px-4 py-3">
              <span className="text-lg text-gray-400 shrink-0">
                {artifact.file_type === 'pdf' ? '\u{1F4C4}' : artifact.file_type === 'pptx' ? '\u{1F4CA}' : '\u{1F4DD}'}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {artifact.original_filename}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {formatSize(artifact.file_size_bytes)}
                </p>
              </div>
              <Badge variant={typeVariant[artifact.file_type] ?? 'default'}>
                {artifact.file_type.toUpperCase()}
              </Badge>
              <StatusBadge status={artifact.status} />
              <a
                href={`/api/files/uploads/artifacts/${artifact.id}`}
                download
                className="text-xs text-primary hover:text-primary-dark transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                Download
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
