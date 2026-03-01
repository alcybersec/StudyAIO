import { PdfViewer } from './PdfViewer'
import type { Artifact } from '../../types'

interface FileViewerProps {
  artifact: Artifact
  targetPage?: number
  navToken?: number
  onPageChange?: (page: number) => void
  onTotalPages?: (total: number) => void
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

const typeIcons: Record<string, string> = {
  pdf: '\u{1F4C4}',
  docx: '\u{1F4DD}',
  pptx: '\u{1F4CA}',
}

function FallbackViewer({ artifact }: { artifact: Artifact }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[300px] bg-gray-50 rounded-lg border border-gray-200">
      <span className="text-5xl mb-4">{typeIcons[artifact.file_type] ?? '\u{1F4C1}'}</span>
      <p className="text-sm font-medium text-gray-900 mb-1">{artifact.original_filename}</p>
      <p className="text-xs text-gray-500 mb-1">{formatSize(artifact.file_size_bytes)}</p>
      <span className="inline-block px-2 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-600 mb-4">
        {artifact.file_type.toUpperCase()}
      </span>
      <p className="text-xs text-gray-400 mb-3">
        Inline preview not available for this file type
      </p>
      <a
        href={`/api/files/uploads/artifacts/${artifact.id}`}
        download
        className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors min-h-[44px] flex items-center"
      >
        Download to view
      </a>
    </div>
  )
}

export function FileViewer({ artifact, targetPage, navToken, onPageChange, onTotalPages }: FileViewerProps) {
  if (artifact.file_type === 'pdf') {
    return (
      <PdfViewer
        fileUrl={`/api/files/uploads/artifacts/${artifact.id}/view`}
        targetPage={targetPage}
        navToken={navToken}
        onPageChange={onPageChange}
        onTotalPages={onTotalPages}
      />
    )
  }

  return <FallbackViewer artifact={artifact} />
}
