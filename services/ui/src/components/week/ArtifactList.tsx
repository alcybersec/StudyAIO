import { useState } from 'react'
import { ChevronDown, ChevronRight, Download, FileText, Presentation } from 'lucide-react'
import { Badge, StatusBadge } from '../ui'
import type { Artifact } from '../../types'

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

const typeVariant: Record<string, 'info' | 'success' | 'warning' | 'danger' | 'default'> = {
  pdf: 'danger',
  docx: 'info',
  pptx: 'warning',
}

interface ArtifactListProps {
  artifacts: Artifact[]
  selectedArtifactId?: string | null
  onSelectArtifact?: (artifactId: string) => void
}

export function ArtifactList({ artifacts, selectedArtifactId, onSelectArtifact }: ArtifactListProps) {
  const [expanded, setExpanded] = useState(true)

  if (artifacts.length === 0) {
    return <p className="text-sm text-text-muted py-4">No source artifacts for this week.</p>
  }

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-semibold text-text-muted hover:text-text mb-3 transition-colors"
        aria-expanded={expanded}
      >
        {expanded ? <ChevronDown size={14} aria-hidden /> : <ChevronRight size={14} aria-hidden />}
        Source files ({artifacts.length})
      </button>
      {expanded && (
        <ul className="divide-y divide-border bg-surface-1 rounded-xl border border-border">
          {artifacts.map((artifact) => {
            const isSelected = selectedArtifactId === artifact.id
            const Icon = artifact.file_type === 'pptx' ? Presentation : FileText
            return (
              <li
                key={artifact.id}
                className={`flex items-center gap-3 px-4 py-3 transition-colors ${
                  onSelectArtifact ? 'cursor-pointer hover:bg-surface-2' : ''
                } ${isSelected ? 'bg-peri-soft border-l-2 border-l-peri' : ''}`}
                onClick={() => onSelectArtifact?.(artifact.id)}
              >
                <Icon size={16} className="text-text-faint shrink-0" aria-hidden />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium truncate ${isSelected ? 'text-peri-fg' : 'text-text'}`}>
                    {artifact.original_filename}
                  </p>
                  <p className="text-xs text-text-faint mt-0.5">{formatSize(artifact.file_size_bytes)}</p>
                </div>
                <Badge variant={typeVariant[artifact.file_type] ?? 'default'}>
                  {artifact.file_type.toUpperCase()}
                </Badge>
                <StatusBadge status={artifact.status} />
                <a
                  href={`/api/files/uploads/artifacts/${artifact.id}`}
                  download
                  className="inline-flex items-center gap-1 text-xs text-peri-fg hover:underline transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Download size={12} aria-hidden /> Download
                </a>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
