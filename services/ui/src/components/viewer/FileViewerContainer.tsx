import { useEffect, useImperativeHandle, useReducer, useState, type Ref } from 'react'
import { FileViewer } from './FileViewer'
import { FileViewerToolbar } from './FileViewerToolbar'
import { ViewerErrorBoundary } from './ViewerErrorBoundary'
import { ViewOriginalModal } from './ViewOriginalModal'
import { initViewerState, viewerReducer, type ViewerAction, type ViewerState } from './viewerReducer'
import type { Artifact } from '../../types'

export interface ViewerStateSnapshot {
  artifactId: string | null
  page: number
  open: boolean
}

/** Imperative surface for the page header buttons / citation links. */
export interface ViewerHandle {
  openAt: (artifactId: string, page: number) => void
  select: (artifactId: string) => void
  toggleOpen: () => void
  openMobile: () => void
}

interface FileViewerContainerProps {
  artifacts: Artifact[]
  initialArtifactId?: string | null
  initialPage?: number
  initialOpen?: boolean
  onStateChange?: (snapshot: ViewerStateSnapshot) => void
  handleRef?: Ref<ViewerHandle>
}

interface ViewerBodyProps {
  artifacts: Artifact[]
  artifact: Artifact
  state: ViewerState
  dispatch: (action: ViewerAction) => void
}

function ViewerBody({ artifacts, artifact, state, dispatch }: ViewerBodyProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.target instanceof HTMLElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
    if (e.key === 'ArrowLeft') dispatch({ type: 'go_to_page', page: state.page - 1 })
    else if (e.key === 'ArrowRight') dispatch({ type: 'go_to_page', page: state.page + 1 })
    else if (e.key === '+' || e.key === '=') dispatch({ type: 'zoom_in' })
    else if (e.key === '-') dispatch({ type: 'zoom_out' })
    else return
    e.preventDefault()
  }

  return (
    // Keyboard shortcuts mirror the Kbd hints shown on the toolbar buttons
    <div className="flex flex-col h-full bg-surface-0 overflow-hidden" onKeyDown={handleKeyDown}>
      <FileViewerToolbar
        artifacts={artifacts}
        selectedArtifact={artifact}
        onSelectArtifact={(id) => dispatch({ type: 'select_artifact', artifactId: id })}
        page={state.page}
        totalPages={state.totalPages}
        zoom={state.zoom}
        onPrevPage={() => dispatch({ type: 'go_to_page', page: state.page - 1 })}
        onNextPage={() => dispatch({ type: 'go_to_page', page: state.page + 1 })}
        onZoomIn={() => dispatch({ type: 'zoom_in' })}
        onZoomOut={() => dispatch({ type: 'zoom_out' })}
      />
      <div className="flex-1 overflow-hidden">
        <FileViewer
          artifact={artifact}
          targetPage={state.targetPage}
          navToken={state.nav}
          zoom={state.zoom}
          onPageChange={(page) => dispatch({ type: 'page_viewed', page })}
          onTotalPages={(total) => dispatch({ type: 'doc_loaded', totalPages: total })}
        />
      </div>
      {state.totalPages > 0 && (
        <div className="flex items-center justify-center px-3 py-1.5 border-t border-border bg-surface-1">
          <span className="font-mono text-[11px] text-text-faint">
            page {state.page} / {state.totalPages}
          </span>
        </div>
      )}
    </div>
  )
}

/**
 * Owns the whole viewer region: artifact selection, PDF chrome, zoom and page
 * state — all folded into a single reducer. The week page only mirrors the
 * pieces it needs for layout and URL sync via `onStateChange`.
 */
export function FileViewerContainer({
  artifacts,
  initialArtifactId,
  initialPage,
  initialOpen,
  onStateChange,
  handleRef,
}: FileViewerContainerProps) {
  const [state, dispatch] = useReducer(
    viewerReducer,
    { artifacts, initialArtifactId, initialPage, initialOpen },
    initViewerState,
  )
  const [mobileOpen, setMobileOpen] = useState(false)

  useImperativeHandle(
    handleRef,
    () => ({
      openAt: (artifactId, page) => dispatch({ type: 'open_at', artifactId, page }),
      select: (artifactId) => dispatch({ type: 'select_artifact', artifactId }),
      toggleOpen: () => dispatch({ type: 'toggle_open' }),
      openMobile: () => setMobileOpen(true),
    }),
    [],
  )

  const { artifactId, page, open } = state
  useEffect(() => {
    onStateChange?.({ artifactId, page, open })
  }, [artifactId, page, open, onStateChange])

  // If the selected artifact left this week (e.g. reclassified away), fall back
  const artifact = artifacts.find((a) => a.id === state.artifactId) ?? artifacts[0] ?? null
  if (!artifact) return null

  return (
    <>
      {open && (
        <div
          className="hidden lg:flex lg:flex-col lg:sticky lg:top-4 lg:self-start rounded-xl border border-border overflow-hidden"
          style={{ height: 'calc(100vh - 8rem)' }}
        >
          <ViewerErrorBoundary>
            <ViewerBody artifacts={artifacts} artifact={artifact} state={state} dispatch={dispatch} />
          </ViewerErrorBoundary>
        </div>
      )}

      <ViewOriginalModal open={mobileOpen} onClose={() => setMobileOpen(false)}>
        <ViewerErrorBoundary>
          <ViewerBody artifacts={artifacts} artifact={artifact} state={state} dispatch={dispatch} />
        </ViewerErrorBoundary>
      </ViewOriginalModal>
    </>
  )
}
