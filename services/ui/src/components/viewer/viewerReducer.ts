import type { Artifact } from '../../types'

export const ZOOM_MIN = 50
export const ZOOM_MAX = 200
export const ZOOM_STEP = 25

/**
 * Single source of truth for the file-viewer region.
 *
 * `page` tracks the page currently in view; `targetPage` + `nav` form a
 * navigation command (the nav counter forces a re-scroll even when the
 * commanded page number is unchanged). Scroll-observation updates `page`
 * only, so watching the user scroll never issues a scroll command back.
 */
export interface ViewerState {
  artifactId: string | null
  page: number
  zoom: number
  open: boolean
  totalPages: number
  targetPage: number
  nav: number
}

export type ViewerAction =
  | { type: 'select_artifact'; artifactId: string }
  | { type: 'go_to_page'; page: number }
  | { type: 'page_viewed'; page: number }
  | { type: 'doc_loaded'; totalPages: number }
  | { type: 'zoom_in' }
  | { type: 'zoom_out' }
  | { type: 'toggle_open' }
  | { type: 'set_open'; open: boolean }
  | { type: 'open_at'; artifactId: string; page: number }

function clampPage(page: number, totalPages: number): number {
  const floor = Math.max(1, Math.floor(page))
  return totalPages > 0 ? Math.min(floor, totalPages) : floor
}

export function viewerReducer(state: ViewerState, action: ViewerAction): ViewerState {
  switch (action.type) {
    case 'select_artifact': {
      if (action.artifactId === state.artifactId) return state
      return {
        ...state,
        artifactId: action.artifactId,
        page: 1,
        targetPage: 1,
        totalPages: 0,
        nav: state.nav + 1,
      }
    }
    case 'go_to_page': {
      const page = clampPage(action.page, state.totalPages)
      return { ...state, page, targetPage: page, nav: state.nav + 1 }
    }
    case 'page_viewed':
      return action.page === state.page ? state : { ...state, page: action.page }
    case 'doc_loaded':
      return { ...state, totalPages: action.totalPages }
    case 'zoom_in':
      return { ...state, zoom: Math.min(state.zoom + ZOOM_STEP, ZOOM_MAX) }
    case 'zoom_out':
      return { ...state, zoom: Math.max(state.zoom - ZOOM_STEP, ZOOM_MIN) }
    case 'toggle_open':
      return { ...state, open: !state.open }
    case 'set_open':
      return state.open === action.open ? state : { ...state, open: action.open }
    case 'open_at': {
      const changingArtifact = action.artifactId !== state.artifactId
      const page = changingArtifact ? Math.max(1, Math.floor(action.page)) : clampPage(action.page, state.totalPages)
      return {
        ...state,
        open: true,
        artifactId: action.artifactId,
        page,
        targetPage: page,
        totalPages: changingArtifact ? 0 : state.totalPages,
        nav: state.nav + 1,
      }
    }
  }
}

export interface ViewerInit {
  artifacts: Artifact[]
  initialArtifactId?: string | null
  initialPage?: number
  initialOpen?: boolean
}

/** Prefer the deep-linked artifact, else the first PDF, else the first file. */
export function initViewerState({ artifacts, initialArtifactId, initialPage, initialOpen }: ViewerInit): ViewerState {
  const linked = initialArtifactId ? artifacts.find((a) => a.id === initialArtifactId) : undefined
  const fallback = artifacts.find((a) => a.file_type === 'pdf') ?? artifacts[0]
  const page = Math.max(1, Math.floor(initialPage ?? 1))
  return {
    artifactId: (linked ?? fallback)?.id ?? null,
    page,
    zoom: 100,
    open: initialOpen ?? false,
    totalPages: 0,
    targetPage: page,
    nav: 1,
  }
}

/**
 * Parse `?artifact=&page=` deep-link params. A missing or non-numeric page
 * falls back to 1 so a mangled link still lands somewhere sensible.
 */
export function parseViewerParams(params: URLSearchParams): { artifactId: string | null; page: number } {
  const artifactId = params.get('artifact')
  const rawPage = params.get('page')
  const parsed = rawPage !== null ? Number(rawPage) : NaN
  const page = Number.isFinite(parsed) && parsed >= 1 ? Math.floor(parsed) : 1
  return { artifactId: artifactId || null, page }
}
