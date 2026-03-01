import { useEffect, useCallback } from 'react'
import { FileViewer } from './FileViewer'
import { FileViewerToolbar } from './FileViewerToolbar'
import type { Artifact } from '../../types'

interface ViewOriginalModalProps {
  open: boolean
  onClose: () => void
  artifacts: Artifact[]
  selectedArtifact: Artifact | null
  onSelectArtifact: (artifactId: string) => void
  targetPage?: number
  navToken?: number
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  onTotalPages: (total: number) => void
  onGoToPage: (page: number) => void
}

export function ViewOriginalModal({
  open,
  onClose,
  artifacts,
  selectedArtifact,
  onSelectArtifact,
  targetPage,
  navToken,
  currentPage,
  totalPages,
  onPageChange,
  onTotalPages,
  onGoToPage,
}: ViewOriginalModalProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose],
  )

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [open, handleKeyDown])

  if (!open || !selectedArtifact) return null

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-white shrink-0">
        <FileViewerToolbar
          artifacts={artifacts}
          selectedArtifact={selectedArtifact}
          onSelectArtifact={onSelectArtifact}
          currentPage={currentPage}
          totalPages={totalPages}
          onGoToPage={onGoToPage}
        />
        <button
          onClick={onClose}
          className="ml-2 p-2 rounded-lg hover:bg-gray-100 transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center text-gray-500"
          aria-label="Close viewer"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Viewer */}
      <div className="flex-1 overflow-hidden">
        <FileViewer
          artifact={selectedArtifact}
          targetPage={targetPage}
          navToken={navToken}
          onPageChange={onPageChange}
          onTotalPages={onTotalPages}
        />
      </div>
    </div>
  )
}
