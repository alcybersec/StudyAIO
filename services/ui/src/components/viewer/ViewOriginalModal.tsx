import * as Dialog from '@radix-ui/react-dialog'
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
  if (!selectedArtifact) return null

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className="fixed inset-0 z-50 flex flex-col bg-surface focus:outline-none">
          <Dialog.Title className="sr-only">View Original Document</Dialog.Title>

          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface shrink-0">
            <FileViewerToolbar
              artifacts={artifacts}
              selectedArtifact={selectedArtifact}
              onSelectArtifact={onSelectArtifact}
              currentPage={currentPage}
              totalPages={totalPages}
              onGoToPage={onGoToPage}
            />
            <Dialog.Close asChild>
              <button
                className="ml-2 p-2 rounded-lg hover:bg-surface-alt transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center text-text-muted"
                aria-label="Close viewer"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </Dialog.Close>
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
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
