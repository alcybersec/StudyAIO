import { Download, FileText, Presentation } from 'lucide-react'
import { PdfViewer } from './PdfViewer'
import type { Artifact } from '../../types'

interface FileViewerProps {
  artifact: Artifact
  targetPage?: number
  navToken?: number
  zoom?: number
  onPageChange?: (page: number) => void
  onTotalPages?: (total: number) => void
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

function FallbackViewer({ artifact }: { artifact: Artifact }) {
  const Icon = artifact.file_type === 'pptx' ? Presentation : FileText
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[300px] bg-surface-0">
      <Icon size={40} strokeWidth={1.25} className="text-text-faint mb-4" aria-hidden />
      <p className="text-sm font-medium text-text mb-1">{artifact.original_filename}</p>
      <p className="text-xs text-text-muted mb-1">{formatSize(artifact.file_size_bytes)}</p>
      <span className="inline-block px-2 py-0.5 font-mono text-[11px] rounded bg-surface-2 text-text-muted mb-4">
        {artifact.file_type.toUpperCase()}
      </span>
      <p className="text-xs text-text-faint mb-3">Inline preview not available for this file type</p>
      <a
        href={`/api/files/uploads/artifacts/${artifact.id}`}
        download
        className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-on-accent bg-sage rounded-lg hover:bg-sage-hover transition-colors min-h-[44px]"
      >
        <Download size={14} aria-hidden /> Download to view
      </a>
    </div>
  )
}

export function FileViewer({ artifact, targetPage, navToken, zoom, onPageChange, onTotalPages }: FileViewerProps) {
  if (artifact.file_type === 'pdf') {
    return (
      <PdfViewer
        fileUrl={`/api/files/uploads/artifacts/${artifact.id}/view`}
        targetPage={targetPage}
        navToken={navToken}
        zoom={zoom}
        onPageChange={onPageChange}
        onTotalPages={onTotalPages}
      />
    )
  }

  return <FallbackViewer artifact={artifact} />
}
