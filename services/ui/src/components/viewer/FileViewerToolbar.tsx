import type { Artifact } from '../../types'

interface FileViewerToolbarProps {
  artifacts: Artifact[]
  selectedArtifact: Artifact | null
  onSelectArtifact: (artifactId: string) => void
  currentPage: number
  totalPages: number
  onGoToPage: (page: number) => void
}

export function FileViewerToolbar({
  artifacts,
  selectedArtifact,
  onSelectArtifact,
  currentPage,
  totalPages,
  onGoToPage,
}: FileViewerToolbarProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200 rounded-t-lg">
      {/* Artifact selector */}
      {artifacts.length > 1 ? (
        <select
          value={selectedArtifact?.id ?? ''}
          onChange={(e) => onSelectArtifact(e.target.value)}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white min-h-[36px] max-w-[200px] truncate"
        >
          {artifacts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.original_filename}
            </option>
          ))}
        </select>
      ) : (
        <span className="text-sm font-medium text-gray-700 truncate max-w-[200px]">
          {selectedArtifact?.original_filename ?? 'No file'}
        </span>
      )}

      <div className="flex-1" />

      {/* Page navigation */}
      {totalPages > 0 && (
        <div className="flex items-center gap-1">
          <button
            onClick={() => onGoToPage(Math.max(1, currentPage - 1))}
            disabled={currentPage <= 1}
            className="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed min-w-[36px] min-h-[36px] flex items-center justify-center text-gray-600"
            aria-label="Previous page"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-xs text-gray-500 whitespace-nowrap px-1">
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={() => onGoToPage(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage >= totalPages}
            className="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed min-w-[36px] min-h-[36px] flex items-center justify-center text-gray-600"
            aria-label="Next page"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}
