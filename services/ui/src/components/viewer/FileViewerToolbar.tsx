import { ChevronLeft, ChevronRight, FileText, ZoomIn, ZoomOut } from 'lucide-react'
import { Button, Select } from '../ui'
import type { Artifact } from '../../types'

interface FileViewerToolbarProps {
  artifacts: Artifact[]
  selectedArtifact: Artifact | null
  onSelectArtifact: (artifactId: string) => void
  page: number
  totalPages: number
  zoom: number
  onPrevPage: () => void
  onNextPage: () => void
  onZoomIn: () => void
  onZoomOut: () => void
}

export function FileViewerToolbar({
  artifacts,
  selectedArtifact,
  onSelectArtifact,
  page,
  totalPages,
  zoom,
  onPrevPage,
  onNextPage,
  onZoomIn,
  onZoomOut,
}: FileViewerToolbarProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-surface-1">
      <FileText size={13} className="text-text-faint shrink-0" aria-hidden />
      {artifacts.length > 1 ? (
        <Select
          options={artifacts.map((a) => ({ value: a.id, label: a.original_filename }))}
          value={selectedArtifact?.id}
          onValueChange={onSelectArtifact}
          className="max-w-[200px] min-w-0"
        />
      ) : (
        <span className="font-mono text-[11px] text-text-muted truncate">
          {selectedArtifact?.original_filename ?? 'No file'}
        </span>
      )}

      <div className="ml-auto flex items-center gap-1.5 shrink-0">
        <Button variant="ghost" size="sm" aria-label="Zoom out" kbd="-" onClick={onZoomOut}>
          <ZoomOut size={13} aria-hidden />
        </Button>
        <span className="font-mono text-[11px] text-text-faint">{zoom}%</span>
        <Button variant="ghost" size="sm" aria-label="Zoom in" kbd="+" onClick={onZoomIn}>
          <ZoomIn size={13} aria-hidden />
        </Button>
        <span className="w-px h-4 bg-border mx-1" aria-hidden />
        <Button
          variant="ghost"
          size="sm"
          aria-label="Previous page"
          kbd="←"
          onClick={onPrevPage}
          disabled={totalPages > 0 && page <= 1}
        >
          <ChevronLeft size={13} aria-hidden />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Next page"
          kbd="→"
          onClick={onNextPage}
          disabled={totalPages > 0 && page >= totalPages}
        >
          <ChevronRight size={13} aria-hidden />
        </Button>
      </div>
    </div>
  )
}
